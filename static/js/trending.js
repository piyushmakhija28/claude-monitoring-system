/**
 * Trending & Featured Widgets JavaScript
 * Handles loading and displaying trending/featured widgets
 */

let trendingCache = {};
let featuredWidgets = [];

/**
 * Initialize trending system
 */
function initializeTrending() {
    // Load featured widgets
    loadFeaturedWidgets();

    // Load initial trending (24h)
    loadTrending(1);
}

/**
 * Load featured widgets
 */
function loadFeaturedWidgets() {
    fetch('/api/widgets/featured')
        .then(response => response.json())
        .then(data => {
            if (data.success && data.featured && data.featured.length > 0) {
                featuredWidgets = data.featured;
                renderFeaturedCarousel(featuredWidgets);
                document.getElementById('featuredSection').style.display = 'block';
            }
        })
        .catch(error => {
            console.error('Error loading featured widgets:', error);
        });
}

/**
 * Render featured carousel
 */
function renderFeaturedCarousel(widgets) {
    const carousel = document.getElementById('featuredWidgets');

    if (!widgets || widgets.length === 0) {
        document.getElementById('featuredSection').style.display = 'none';
        return;
    }

    let html = '';

    widgets.forEach((widget, index) => {
        html += `
            <div class="carousel-item ${index === 0 ? 'active' : ''}">
                <div class="row">
                    <div class="col-md-8 mx-auto">
                        <div class="featured-widget-card">
                            <div class="row g-0">
                                <div class="col-md-4">
                                    <div class="featured-widget-preview">
                                        <i class="fas fa-star fa-3x text-warning"></i>
                                    </div>
                                </div>
                                <div class="col-md-8">
                                    <div class="featured-widget-info">
                                        <span class="badge bg-warning text-dark mb-2">
                                            <i class="fas fa-star me-1"></i>Featured
                                        </span>
                                        <h4>${escapeHtml(widget.name)}</h4>
                                        <p class="text-muted">By ${escapeHtml(widget.author)}</p>
                                        <p class="featured-description">${escapeHtml(widget.description || 'No description available')}</p>
                                        <div class="d-flex gap-2 mt-3">
                                            <button class="btn btn-primary btn-sm" onclick="viewWidgetDetails('${widget.widget_id}')">
                                                <i class="fas fa-eye me-1"></i>View Details
                                            </button>
                                            <button class="btn btn-outline-primary btn-sm" onclick="downloadWidget('${widget.widget_id}')">
                                                <i class="fas fa-download me-1"></i>Download
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    });

    carousel.innerHTML = html;
}

/**
 * Load trending widgets
 */
function loadTrending(periodDays) {
    const containerId = `trendingWidgets${periodDays === 1 ? '24h' : periodDays + 'd'}`;
    const container = document.getElementById(containerId);

    if (!container) return;

    // Check cache
    if (trendingCache[periodDays]) {
        renderTrendingWidgets(trendingCache[periodDays], container);
        return;
    }

    // Show loading
    container.innerHTML = `
        <div class="text-center text-muted py-4">
            <i class="fas fa-spinner fa-spin fa-2x mb-3"></i>
            <p>Loading trending widgets...</p>
        </div>
    `;

    // Fetch from API
    fetch(`/api/widgets/trending?period=${periodDays}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                trendingCache[periodDays] = data.trending;
                renderTrendingWidgets(data.trending, container);
            } else {
                container.innerHTML = `
                    <div class="alert alert-info">
                        <i class="fas fa-info-circle me-2"></i>No trending widgets found
                    </div>
                `;
            }
        })
        .catch(error => {
            console.error('Error loading trending:', error);
            container.innerHTML = `
                <div class="alert alert-danger">
                    <i class="fas fa-exclamation-circle me-2"></i>Error loading trending widgets
                </div>
            `;
        });
}

/**
 * Render trending widgets
 */
function renderTrendingWidgets(widgets, container) {
    if (!widgets || widgets.length === 0) {
        container.innerHTML = `
            <div class="alert alert-info">
                <i class="fas fa-info-circle me-2"></i>No trending widgets found for this period
            </div>
        `;
        return;
    }

    let html = '';

    widgets.slice(0, 6).forEach((widget, index) => {
        const trendIcon = getTrendIcon(widget.trend);
        const rankBadge = getRankBadge(widget.rank);

        html += `
            <div class="trending-widget-card" onclick="viewWidgetDetails('${widget.widget_id}')">
                <div class="trending-rank">
                    ${rankBadge}
                    <span class="trend-indicator ${widget.trend}">
                        ${trendIcon}
                    </span>
                </div>
                <div class="trending-widget-content">
                    <h6 class="widget-name">${escapeHtml(widget.name)}</h6>
                    <p class="widget-author text-muted small mb-2">
                        <i class="fas fa-user me-1"></i>${escapeHtml(widget.author)}
                    </p>
                    <div class="trending-stats">
                        <div class="stat-item">
                            <i class="fas fa-download text-primary"></i>
                            <span>${widget.metrics.downloads}</span>
                        </div>
                        <div class="stat-item">
                            <i class="fas fa-star text-warning"></i>
                            <span>${widget.metrics.rating_weighted.toFixed(1)}</span>
                        </div>
                        <div class="stat-item">
                            <i class="fas fa-comments text-info"></i>
                            <span>${widget.metrics.comment_activity}</span>
                        </div>
                    </div>
                    <div class="trending-score mt-2">
                        <div class="progress" style="height: 4px;">
                            <div class="progress-bar bg-gradient-trending" style="width: ${widget.score}%"></div>
                        </div>
                        <small class="text-muted">Score: ${widget.score.toFixed(1)}</small>
                    </div>
                </div>
            </div>
        `;
    });

    container.innerHTML = html;
}

/**
 * Get trend icon
 */
function getTrendIcon(trend) {
    switch (trend) {
        case 'rising':
            return '<i class="fas fa-arrow-up text-success"></i>';
        case 'declining':
            return '<i class="fas fa-arrow-down text-danger"></i>';
        default:
            return '<i class="fas fa-minus text-secondary"></i>';
    }
}

/**
 * Get rank badge
 */
function getRankBadge(rank) {
    if (rank === 1) {
        return '<span class="rank-badge gold"><i class="fas fa-trophy"></i> 1st</span>';
    } else if (rank === 2) {
        return '<span class="rank-badge silver"><i class="fas fa-medal"></i> 2nd</span>';
    } else if (rank === 3) {
        return '<span class="rank-badge bronze"><i class="fas fa-medal"></i> 3rd</span>';
    } else {
        return `<span class="rank-badge">#${rank}</span>`;
    }
}

/**
 * View widget details
 */
function viewWidgetDetails(widgetId) {
    // This function should already exist in the marketplace
    console.log('View widget:', widgetId);
    // You can implement modal or redirect to widget details page
}

/**
 * Download widget
 */
function downloadWidget(widgetId) {
    // This function should already exist in the marketplace
    fetch(`/api/community-widgets/${widgetId}/download`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Download logic
                alert('Widget downloaded successfully!');

                // Refresh trending to update download counts
                clearTrendingCache();
            } else {
                alert('Error downloading widget: ' + data.message);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Error downloading widget');
        });
}

/**
 * Clear trending cache
 */
function clearTrendingCache() {
    trendingCache = {};
    // Reload current trending view
    const activeTab = document.querySelector('.nav-link.active[data-bs-toggle="tab"]');
    if (activeTab) {
        const period = activeTab.textContent.includes('24h') ? 1 :
                      activeTab.textContent.includes('7d') ? 7 : 30;
        loadTrending(period);
    }
}

/**
 * Recalculate trending (admin only)
 */
function recalculateTrending() {
    if (!confirm('Recalculate trending scores? This will update all trending data.')) {
        return;
    }

    fetch('/api/widgets/trending/calculate', {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('Trending data recalculated successfully!');
            clearTrendingCache();
            loadFeaturedWidgets();
        } else {
            alert('Error recalculating trending: ' + data.message);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error recalculating trending');
    });
}

/**
 * Utility: Escape HTML
 */
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Initialize on page load
 */
document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('featuredSection')) {
        initializeTrending();
    }
});
