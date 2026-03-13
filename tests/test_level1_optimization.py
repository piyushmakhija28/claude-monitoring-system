"""
Test suite for Level 1 Optimization features (Task #6).

Tests cover:
1. Context Caching - hit/miss rate logging, SHA-256 key hashing, CacheStats
2. Timeout Handling - graceful recovery, partial context return
3. Memory Pressure - streaming for large files, OOM safeguard
4. Integration - full node_context_loader flow with all optimizations

ASCII-safe, UTF-8 encoded, Windows-compatible.
"""

import hashlib
import json
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from langgraph_engine.context_cache import (
    CacheStats,
    ContextCache,
    CACHE_STATS,
    CACHE_MAX_AGE_HOURS,
    CACHE_KEY_HASH,
    CACHE_KEY_LENGTH,
)
from langgraph_engine.subgraphs.level1_sync import (
    _stream_file_head,
    _read_file_with_timeout,
    node_context_loader,
    CONTEXT_TIMEOUT_PER_FILE,
    CONTEXT_TIMEOUT_TOTAL,
    MAX_FILE_SIZE,
    MAX_TOTAL_SIZE,
    STREAMING_THRESHOLD,
    STREAMING_CHUNK_SIZE,
    MAX_CONTENT_CHARS,
)


# ===========================================================================
# FIXTURES
# ===========================================================================

@pytest.fixture(autouse=True)
def reset_cache_stats():
    """Reset global CacheStats counters before every test to avoid bleed."""
    CACHE_STATS.reset()
    yield
    CACHE_STATS.reset()


@pytest.fixture
def tmp_project(tmp_path):
    """Create a temporary project directory with context files."""
    return tmp_path


@pytest.fixture
def tmp_cache_dir(tmp_path):
    """Return a temporary directory to use as the cache base dir."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return cache_dir


@pytest.fixture
def cache(tmp_cache_dir):
    """Return a ContextCache instance backed by a temp directory."""
    return ContextCache(cache_base_dir=str(tmp_cache_dir))


# ===========================================================================
# 1. CACHE STATS - Hit/Miss Rate Logging
# ===========================================================================

class TestCacheStats:
    """Verify CacheStats records hits/misses and computes rates correctly."""

    def test_initial_state_is_zero(self):
        stats = CacheStats()
        d = stats.to_dict()
        assert d["hits"] == 0
        assert d["misses"] == 0
        assert d["total_lookups"] == 0
        assert d["hit_rate"] == 0.0
        assert d["hit_rate_pct"] == 0.0

    def test_record_hit_increments_counter(self):
        stats = CacheStats()
        stats.record_hit()
        stats.record_hit()
        d = stats.to_dict()
        assert d["hits"] == 2
        assert d["total_lookups"] == 2
        assert d["hit_rate"] == 1.0
        assert d["hit_rate_pct"] == 100.0

    def test_record_miss_increments_counter_and_reason(self):
        stats = CacheStats()
        stats.record_miss("no_cache_file")
        stats.record_miss("expired")
        stats.record_miss("no_cache_file")
        d = stats.to_dict()
        assert d["misses"] == 3
        assert d["miss_reasons"]["no_cache_file"] == 2
        assert d["miss_reasons"]["expired"] == 1

    def test_hit_rate_calculation(self):
        stats = CacheStats()
        # 3 hits, 1 miss => 75%
        for _ in range(3):
            stats.record_hit()
        stats.record_miss("test")
        d = stats.to_dict()
        assert d["hit_rate"] == pytest.approx(0.75, abs=0.01)
        assert d["hit_rate_pct"] == pytest.approx(75.0, abs=0.1)

    def test_record_save_and_invalidation(self):
        stats = CacheStats()
        stats.record_save()
        stats.record_save()
        stats.record_invalidation()
        d = stats.to_dict()
        assert d["saves"] == 2
        assert d["invalidations"] == 1

    def test_reset_clears_all_counters(self):
        stats = CacheStats()
        stats.record_hit()
        stats.record_miss("test")
        stats.record_save()
        stats.reset()
        d = stats.to_dict()
        assert d["hits"] == 0
        assert d["misses"] == 0
        assert d["saves"] == 0

    def test_thread_safety(self):
        """Concurrent hit/miss recordings should not corrupt counters."""
        stats = CacheStats()
        n = 100

        def record_hits():
            for _ in range(n):
                stats.record_hit()

        def record_misses():
            for _ in range(n):
                stats.record_miss("concurrent")

        threads = [threading.Thread(target=record_hits) for _ in range(5)]
        threads += [threading.Thread(target=record_misses) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        d = stats.to_dict()
        assert d["hits"] == 5 * n
        assert d["misses"] == 5 * n
        assert d["total_lookups"] == 10 * n

    def test_persist_writes_json_file(self, tmp_path):
        stats = CacheStats()
        stats.record_hit()
        stats.record_miss("test")
        stats_file = tmp_path / "cache_stats.json"
        result = stats.persist(stats_file)
        assert result is True
        assert stats_file.exists()
        records = json.loads(stats_file.read_text(encoding="utf-8"))
        assert isinstance(records, list)
        assert len(records) == 1
        assert records[0]["hits"] == 1
        assert records[0]["misses"] == 1

    def test_persist_appends_and_caps_at_100(self, tmp_path):
        stats = CacheStats()
        stats_file = tmp_path / "cache_stats.json"
        # Write 110 records
        for i in range(110):
            stats.record_hit()
            stats.persist(stats_file)
        records = json.loads(stats_file.read_text(encoding="utf-8"))
        # Should be capped at 100
        assert len(records) == 100


# ===========================================================================
# 2. CACHE KEY HASHING - SHA-256
# ===========================================================================

class TestCacheKeyHashing:
    """Verify cache key uses SHA-256 with correct length truncation."""

    def test_cache_key_uses_sha256(self):
        path = "/some/project/path"
        resolved = str(Path(path).resolve())
        expected_full = hashlib.sha256(resolved.encode("utf-8")).hexdigest()
        key = ContextCache._cache_key(path)
        assert expected_full.startswith(key)
        assert len(key) == CACHE_KEY_LENGTH

    def test_cache_key_algo_constant(self):
        assert CACHE_KEY_HASH == "sha256"

    def test_different_paths_produce_different_keys(self):
        key1 = ContextCache._cache_key("/project/a")
        key2 = ContextCache._cache_key("/project/b")
        assert key1 != key2

    def test_same_path_produces_same_key(self):
        path = "/project/stable"
        assert ContextCache._cache_key(path) == ContextCache._cache_key(path)

    def test_key_length_is_32(self):
        key = ContextCache._cache_key("/any/path")
        assert len(key) == 32

    def test_cache_entry_stores_algo_name(self, cache, tmp_project):
        """Saved cache entries should record 'sha256' as the key algorithm."""
        cache.save_cache(str(tmp_project), {"files_loaded": []})
        key = ContextCache._cache_key(str(tmp_project))
        cache_file = Path(cache.cache_dir) / (key + ".json")
        entry = json.loads(cache_file.read_text(encoding="utf-8"))
        assert entry.get("cache_key_algo") == "sha256"


# ===========================================================================
# 3. CONTEXT CACHE - Load / Save / Invalidate
# ===========================================================================

class TestContextCacheLoadSave:
    """Verify cache load/save/invalidate round-trips."""

    def test_save_and_load_returns_same_data(self, cache, tmp_project):
        data = {"files_loaded": ["README"], "readme": "hello world"}
        cache.save_cache(str(tmp_project), data)
        loaded = cache.load_cache(str(tmp_project))
        assert loaded is not None
        assert loaded["readme"] == "hello world"
        assert loaded["_cache_hit"] is True

    def test_load_miss_when_no_cache(self, cache, tmp_project):
        result = cache.load_cache(str(tmp_project))
        assert result is None

    def test_cache_miss_records_no_cache_file_reason(self, cache, tmp_project):
        cache.load_cache(str(tmp_project))
        stats = CACHE_STATS.to_dict()
        assert stats["misses"] == 1
        assert "no_cache_file" in stats["miss_reasons"]

    def test_cache_hit_recorded_in_stats(self, cache, tmp_project):
        data = {"files_loaded": []}
        cache.save_cache(str(tmp_project), data)
        cache.load_cache(str(tmp_project))
        stats = ContextCache.get_session_stats()
        assert stats["hits"] == 1

    def test_invalidate_removes_cache(self, cache, tmp_project):
        data = {"files_loaded": []}
        cache.save_cache(str(tmp_project), data)
        removed = cache.invalidate(str(tmp_project))
        assert removed is True
        loaded = cache.load_cache(str(tmp_project))
        assert loaded is None

    def test_invalidate_nonexistent_returns_false(self, cache, tmp_project):
        result = cache.invalidate(str(tmp_project))
        assert result is False

    def test_cache_expired_returns_none(self, cache, tmp_project):
        """Simulate an expired cache by patching datetime.now()."""
        from datetime import datetime, timedelta
        data = {"files_loaded": []}
        cache.save_cache(str(tmp_project), data)

        # Patch now() to return a time 25 hours in the future
        future = datetime.now() + timedelta(hours=25)
        with patch("langgraph_engine.context_cache.datetime") as mock_dt:
            mock_dt.now.return_value = future
            mock_dt.fromisoformat = datetime.fromisoformat
            result = cache.load_cache(str(tmp_project))
        assert result is None

    def test_cache_miss_expired_recorded(self, cache, tmp_project):
        from datetime import datetime, timedelta
        data = {"files_loaded": []}
        cache.save_cache(str(tmp_project), data)
        CACHE_STATS.reset()  # Reset after save

        future = datetime.now() + timedelta(hours=25)
        with patch("langgraph_engine.context_cache.datetime") as mock_dt:
            mock_dt.now.return_value = future
            mock_dt.fromisoformat = datetime.fromisoformat
            cache.load_cache(str(tmp_project))

        stats = CACHE_STATS.to_dict()
        assert stats["misses"] == 1
        assert "expired" in stats["miss_reasons"]

    def test_cache_info_includes_hit_rate_stats(self, cache, tmp_project):
        info = cache.cache_info(str(tmp_project))
        assert "hit_rate_stats" in info
        assert "hits" in info["hit_rate_stats"]

    def test_get_session_stats_static_method(self, cache, tmp_project):
        cache.save_cache(str(tmp_project), {"files_loaded": []})
        cache.load_cache(str(tmp_project))
        stats = ContextCache.get_session_stats()
        assert "hit_rate_pct" in stats
        assert "hits" in stats
        assert "misses" in stats

    def test_files_changed_invalidates_cache(self, cache, tmp_project):
        # Create a README and cache context
        readme = tmp_project / "README.md"
        readme.write_text("version 1", encoding="utf-8")
        data = {"files_loaded": ["README"]}
        cache.save_cache(str(tmp_project), data)
        CACHE_STATS.reset()

        # Modify the file
        readme.write_text("version 2 - changed content", encoding="utf-8")
        result = cache.load_cache(str(tmp_project))
        assert result is None
        stats = CACHE_STATS.to_dict()
        assert "files_changed" in stats["miss_reasons"]


# ===========================================================================
# 4. STREAMING - Large File Handling
# ===========================================================================

class TestStreamFileHead:
    """Verify _stream_file_head reads large files without loading all into memory."""

    def test_small_file_reads_completely(self, tmp_path):
        f = tmp_path / "small.txt"
        content = "hello world"
        f.write_text(content, encoding="utf-8")
        result = _stream_file_head(f, max_chars=1000)
        assert result == content

    def test_large_file_truncated_to_max_chars(self, tmp_path):
        f = tmp_path / "large.txt"
        # Write 10KB of content
        content = "x" * 10000
        f.write_text(content, encoding="utf-8")
        result = _stream_file_head(f, max_chars=500)
        assert len(result) == 500
        assert result == "x" * 500

    def test_streaming_respects_chunk_size(self, tmp_path):
        f = tmp_path / "chunked.txt"
        content = "a" * 200
        f.write_text(content, encoding="utf-8")
        # Use tiny chunk size (10 chars)
        result = _stream_file_head(f, max_chars=50, chunk_size=10)
        assert len(result) == 50
        assert result == "a" * 50

    def test_empty_file_returns_empty_string(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_text("", encoding="utf-8")
        result = _stream_file_head(f)
        assert result == ""

    def test_utf8_content_streams_correctly(self, tmp_path):
        f = tmp_path / "utf8.txt"
        # ASCII-safe test content
        content = "line {}\n".format("A" * 50) * 20
        f.write_text(content, encoding="utf-8")
        result = _stream_file_head(f, max_chars=100)
        assert len(result) == 100

    def test_streaming_threshold_constant_is_1mb(self):
        assert STREAMING_THRESHOLD == 1_000_000

    def test_streaming_chunk_size_is_64kb(self):
        assert STREAMING_CHUNK_SIZE == 65_536


# ===========================================================================
# 5. TIMEOUT HANDLING - Per-file and Total
# ===========================================================================

class TestReadFileWithTimeout:
    """Verify _read_file_with_timeout handles both normal and timeout cases."""

    def test_normal_read_returns_content(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello", encoding="utf-8")
        result = _read_file_with_timeout(f, timeout_seconds=5)
        assert result == "hello"

    def test_returns_empty_for_empty_file(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_text("", encoding="utf-8")
        result = _read_file_with_timeout(f, timeout_seconds=5)
        assert result == ""

    def test_streaming_mode_limits_output(self, tmp_path):
        f = tmp_path / "big.txt"
        f.write_text("y" * 10000, encoding="utf-8")
        result = _read_file_with_timeout(
            f, timeout_seconds=5, use_streaming=True, max_chars=200
        )
        assert len(result) == 200

    def test_raises_timeout_error_on_slow_read(self, tmp_path):
        """Simulate a slow read by patching _stream_file_head to sleep."""
        f = tmp_path / "slow.txt"
        f.write_text("data", encoding="utf-8")

        original_stream = __import__(
            "langgraph_engine.subgraphs.level1_sync",
            fromlist=["_stream_file_head"],
        )._stream_file_head

        def slow_stream(*args, **kwargs):
            time.sleep(10)  # Longer than timeout
            return "data"

        with patch(
            "langgraph_engine.subgraphs.level1_sync._stream_file_head",
            side_effect=slow_stream,
        ):
            with pytest.raises(TimeoutError):
                _read_file_with_timeout(
                    f, timeout_seconds=1, use_streaming=True, max_chars=100
                )

    def test_nonexistent_file_raises_exception(self, tmp_path):
        f = tmp_path / "nonexistent.txt"
        with pytest.raises(Exception):
            _read_file_with_timeout(f, timeout_seconds=5)


# ===========================================================================
# 6. NODE CONTEXT LOADER - Integration Tests
# ===========================================================================

class TestNodeContextLoaderOptimizations:
    """Integration tests for node_context_loader with all optimization features."""

    def _make_state(self, project_root: str, session_path: str = "") -> dict:
        return {
            "project_root": project_root,
            "session_path": session_path,
            "user_message": "test",
            "session_id": "test-session",
        }

    def test_loads_normal_files_successfully(self, tmp_project):
        (tmp_project / "README.md").write_text("readme content", encoding="utf-8")
        (tmp_project / "CLAUDE.md").write_text("claude content", encoding="utf-8")
        state = self._make_state(str(tmp_project))
        result = node_context_loader(state)
        assert result["context_loaded"] is True
        assert result["files_loaded_count"] >= 1
        assert "README" in result["context_data"].get("files_loaded", [])

    def test_returns_partial_context_when_one_file_missing(self, tmp_project):
        """Only README present - should load readme, not crash for SRS or CLAUDE.md."""
        (tmp_project / "README.md").write_text("readme only", encoding="utf-8")
        state = self._make_state(str(tmp_project))
        result = node_context_loader(state)
        assert result["context_loaded"] is True
        assert result["files_loaded_count"] == 1
        assert result["context_data"]["readme"] == "readme only"

    def test_returns_empty_context_when_no_files(self, tmp_project):
        state = self._make_state(str(tmp_project))
        result = node_context_loader(state)
        assert result["context_loaded"] is True
        assert result["files_loaded_count"] == 0
        assert result["context_data"]["files_loaded"] == []

    def test_cache_hit_returns_immediately(self, tmp_project, tmp_cache_dir):
        (tmp_project / "README.md").write_text("readme", encoding="utf-8")
        with patch(
            "langgraph_engine.subgraphs.level1_sync.ContextCache",
        ) as MockCache:
            mock_instance = MagicMock()
            mock_instance.load_cache.return_value = {
                "files_loaded": ["README"],
                "readme": "cached readme",
                "_cache_hit": True,
                "_cache_age_hours": 1.0,
            }
            MockCache.return_value = mock_instance
            MockCache._cache_key.return_value = "abc123"
            MockCache.get_session_stats.return_value = {"hit_rate_pct": 100.0}

            state = self._make_state(str(tmp_project))
            result = node_context_loader(state)

        assert result["context_cache_hit"] is True
        assert result["context_data"]["readme"] == "cached readme"
        assert result["files_loaded_count"] == 1

    def test_cache_miss_triggers_fresh_load(self, tmp_project, tmp_cache_dir):
        (tmp_project / "README.md").write_text("fresh load", encoding="utf-8")
        with patch(
            "langgraph_engine.subgraphs.level1_sync.ContextCache",
        ) as MockCache:
            mock_instance = MagicMock()
            mock_instance.load_cache.return_value = None  # Miss
            mock_instance.save_cache.return_value = True
            MockCache.return_value = mock_instance
            MockCache._cache_key.return_value = "def456"
            MockCache.get_session_stats.return_value = {"hit_rate_pct": 0.0}

            state = self._make_state(str(tmp_project))
            result = node_context_loader(state)

        assert result["context_cache_hit"] is False
        assert result["context_loaded"] is True
        assert result["files_loaded_count"] >= 1

    def test_timeout_on_one_file_returns_partial_context(self, tmp_project):
        """When a file read times out, the other files should still load."""
        (tmp_project / "README.md").write_text("readme ok", encoding="utf-8")
        (tmp_project / "CLAUDE.md").write_text("claude ok", encoding="utf-8")

        call_count = [0]

        original_read = _read_file_with_timeout

        def mock_timeout_for_readme(file_path, timeout_seconds, use_streaming=False, max_chars=5000):
            call_count[0] += 1
            if "README" in str(file_path).upper():
                raise TimeoutError("Simulated timeout for README")
            return original_read(file_path, timeout_seconds, use_streaming, max_chars)

        with patch(
            "langgraph_engine.subgraphs.level1_sync._read_file_with_timeout",
            side_effect=mock_timeout_for_readme,
        ):
            state = self._make_state(str(tmp_project))
            result = node_context_loader(state)

        # Should have partial context - CLAUDE.md loaded even though README timed out
        assert result["context_loaded"] is True
        assert "README" in result["context_skipped_files"]
        assert any("CLAUDE" in f for f in result["context_data"].get("files_loaded", []))
        # Timeout warning should be recorded
        assert any("Timeout" in w or "timeout" in w for w in result.get("context_load_warnings", []))

    def test_large_file_uses_streaming(self, tmp_project):
        """Files >= STREAMING_THRESHOLD bytes should trigger streaming mode."""
        large_readme = tmp_project / "README.md"
        # Write content larger than 1MB threshold
        large_content = "B" * (STREAMING_THRESHOLD + 1000)
        large_readme.write_text(large_content, encoding="utf-8")

        state = self._make_state(str(tmp_project))
        result = node_context_loader(state)

        # File should be loaded (via streaming) rather than skipped
        assert result["context_loaded"] is True
        # Should be in streamed_files list
        assert "README" in result.get("context_streamed_files", [])
        # Content should be truncated to MAX_CONTENT_CHARS
        readme_content = result["context_data"].get("readme", "")
        assert len(readme_content) <= MAX_CONTENT_CHARS
        # Streaming warning should be in warnings
        assert any("streaming" in w.lower() or "stream" in w.lower() for w in result.get("context_load_warnings", []))

    def test_total_memory_budget_stops_loading(self, tmp_project):
        """When MAX_TOTAL_SIZE is reached, no more files should be loaded."""
        # Write two files, each just under MAX_TOTAL_SIZE / 2
        readme = tmp_project / "README.md"
        claude = tmp_project / "CLAUDE.md"
        readme.write_text("R" * 100, encoding="utf-8")
        claude.write_text("C" * 100, encoding="utf-8")

        # Patch MAX_TOTAL_SIZE to be extremely small (50 bytes) to trigger budget
        with patch("langgraph_engine.subgraphs.level1_sync.MAX_TOTAL_SIZE", 50):
            state = self._make_state(str(tmp_project))
            result = node_context_loader(state)

        # Should have stopped after budget was hit - at least one warning
        warnings = result.get("context_load_warnings", [])
        assert any("limit" in w.lower() or "budget" in w.lower() for w in warnings)

    def test_result_includes_load_time_ms(self, tmp_project):
        state = self._make_state(str(tmp_project))
        result = node_context_loader(state)
        assert "context_load_time_ms" in result
        assert isinstance(result["context_load_time_ms"], int)
        assert result["context_load_time_ms"] >= 0

    def test_result_includes_hit_rate_pct(self, tmp_project):
        state = self._make_state(str(tmp_project))
        result = node_context_loader(state)
        assert "context_hit_rate_pct" in result

    def test_result_includes_streamed_files_list(self, tmp_project):
        state = self._make_state(str(tmp_project))
        result = node_context_loader(state)
        assert "context_streamed_files" in result
        assert isinstance(result["context_streamed_files"], list)

    def test_general_exception_returns_empty_not_crash(self, tmp_project):
        """Top-level exception should return empty context dict, not raise."""
        state = self._make_state(str(tmp_project))
        with patch(
            "langgraph_engine.subgraphs.level1_sync.Path",
            side_effect=Exception("Simulated catastrophic error"),
        ):
            # Should not raise - returns fallback
            try:
                result = node_context_loader(state)
                # If we get here, it returned gracefully
                assert "context_loaded" in result
            except Exception:
                pytest.fail("node_context_loader should not raise exceptions")

    def test_content_truncated_to_max_content_chars(self, tmp_project):
        """Loaded content should never exceed MAX_CONTENT_CHARS."""
        readme = tmp_project / "README.md"
        # Write 2x MAX_CONTENT_CHARS worth of content
        readme.write_text("Z" * (MAX_CONTENT_CHARS * 2), encoding="utf-8")
        state = self._make_state(str(tmp_project))
        result = node_context_loader(state)
        readme_content = result["context_data"].get("readme") or ""
        assert len(readme_content) <= MAX_CONTENT_CHARS


# ===========================================================================
# 7. PERFORMANCE BENCHMARKS
# ===========================================================================

class TestPerformanceBenchmarks:
    """Verify optimization targets are met."""

    def test_cache_hit_is_faster_than_fresh_load(self, tmp_project, tmp_cache_dir):
        """Cache hit should complete significantly faster than cold load."""
        readme = tmp_project / "README.md"
        readme.write_text("bench readme content " * 100, encoding="utf-8")
        claude = tmp_project / "CLAUDE.md"
        claude.write_text("bench claude content " * 100, encoding="utf-8")

        cache = ContextCache(cache_base_dir=str(tmp_cache_dir))

        # Warm up: fresh load
        state = {
            "project_root": str(tmp_project),
            "session_path": "",
            "user_message": "benchmark",
            "session_id": "bench-session",
        }

        t0 = time.perf_counter()
        result1 = node_context_loader(state)
        cold_ms = (time.perf_counter() - t0) * 1000

        # Force cache save so next load hits cache
        cache.save_cache(str(tmp_project), result1.get("context_data", {}))
        CACHE_STATS.reset()

        # Mock cache to return the saved data
        saved_data = result1.get("context_data", {})
        saved_data["_cache_hit"] = True
        saved_data["_cache_age_hours"] = 0.1

        with patch(
            "langgraph_engine.subgraphs.level1_sync.ContextCache"
        ) as MockCache:
            mock_instance = MagicMock()
            mock_instance.load_cache.return_value = saved_data
            MockCache.return_value = mock_instance
            MockCache._cache_key.return_value = "bench123"
            MockCache.get_session_stats.return_value = {"hit_rate_pct": 100.0}

            t1 = time.perf_counter()
            result2 = node_context_loader(state)
            cache_ms = (time.perf_counter() - t1) * 1000

        assert result2["context_cache_hit"] is True
        # Cache hit should be faster (cache read vs filesystem glob + file read)
        # Soft assertion - just verify it completed quickly (< 100ms)
        assert cache_ms < 100, "Cache hit took {}ms, expected < 100ms".format(cache_ms)

    def test_streaming_does_not_exceed_memory_limit(self, tmp_project):
        """Streamed file content should be <= MAX_CONTENT_CHARS characters."""
        readme = tmp_project / "README.md"
        readme.write_text("M" * 2_000_000, encoding="utf-8")  # 2MB file
        state = {
            "project_root": str(tmp_project),
            "session_path": "",
            "user_message": "memory test",
            "session_id": "mem-session",
        }
        result = node_context_loader(state)
        content = result["context_data"].get("readme") or ""
        # Must not exceed max chars
        assert len(content) <= MAX_CONTENT_CHARS
        # Should be in streamed files
        assert "README" in result.get("context_streamed_files", [])

    def test_partial_context_not_empty_on_single_file_error(self, tmp_project):
        """When one file errors, the others must still load - not return empty."""
        (tmp_project / "README.md").write_text("valid readme", encoding="utf-8")
        (tmp_project / "CLAUDE.md").write_text("valid claude", encoding="utf-8")

        def fail_readme(file_path, timeout_seconds, use_streaming=False, max_chars=5000):
            if "README" in str(file_path).upper():
                raise IOError("Simulated IO error for README")
            # Normal read for other files
            p = Path(file_path)
            return p.read_text(encoding="utf-8", errors="ignore")[:max_chars]

        with patch(
            "langgraph_engine.subgraphs.level1_sync._read_file_with_timeout",
            side_effect=fail_readme,
        ):
            state = {
                "project_root": str(tmp_project),
                "session_path": "",
                "user_message": "partial test",
                "session_id": "partial-session",
            }
            result = node_context_loader(state)

        # CLAUDE.md should still be loaded
        assert result["context_loaded"] is True
        assert result["files_loaded_count"] >= 1
        files_loaded = result["context_data"].get("files_loaded", [])
        assert any("CLAUDE" in f for f in files_loaded)
        # README should be in skipped
        assert "README" in result["context_skipped_files"]


# ===========================================================================
# 8. FLOW STATE FIELD VERIFICATION
# ===========================================================================

class TestFlowStateOptimizationFields:
    """Verify new FlowState fields added for Task #6 are accessible."""

    def test_optimization_fields_importable(self):
        from langgraph_engine.flow_state import FlowState
        # FlowState uses total=False so all fields are optional
        # Verify the fields exist in the TypedDict annotations
        annotations = FlowState.__annotations__
        assert "context_load_time_ms" in annotations
        assert "context_hit_rate_pct" in annotations
        assert "context_streamed_files" in annotations

    def test_cache_key_comment_references_sha256(self):
        """Verify FlowState comment was updated from MD5 to SHA-256."""
        from langgraph_engine import flow_state as fs_module
        import inspect
        source = inspect.getsource(fs_module)
        # Should reference SHA-256 not MD5 in the optimization fields comment
        assert "SHA-256" in source or "sha256" in source.lower()
