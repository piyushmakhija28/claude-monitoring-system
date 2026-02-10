/**
 * Widget Comments JavaScript
 * Handles comment threads, @mentions, reactions, and real-time updates
 */

let comments = [];
let replyingTo = null;
let users = ['admin', 'developer123', 'designer456', 'user789']; // Mock users for autocomplete

/**
 * Initialize comments system
 */
function initializeComments() {
    // Load comments for current widget
    loadComments();

    // Setup @mention autocomplete
    setupMentionAutocomplete();

    // Connect to WebSocket for real-time updates
    connectCommentWebSocket();

    // Handle enter key in comment input
    document.getElementById('newCommentInput').addEventListener('keypress', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            addComment();
        }
    });
}

/**
 * Load comments from API
 */
function loadComments() {
    const widgetId = window.currentWidgetId || 'widget_demo';

    fetch(`/api/widgets/${widgetId}/comments?limit=100`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                comments = data.comments;
                renderComments(comments);
                updateCommentCount(data.total);
            } else {
                console.error('Error loading comments:', data.message);
            }
        })
        .catch(error => {
            console.error('Error loading comments:', error);
        });
}

/**
 * Render comments list
 */
function renderComments(commentsData) {
    const commentsList = document.getElementById('commentsList');

    if (!commentsData || commentsData.length === 0) {
        commentsList.innerHTML = `
            <div class="text-center text-muted py-5">
                <i class="fas fa-comments fa-2x mb-3"></i>
                <p>No comments yet. Be the first to comment!</p>
            </div>
        `;
        return;
    }

    // Group comments by thread
    const threads = groupCommentsByThread(commentsData);

    let html = '';
    threads.forEach(thread => {
        html += renderThread(thread);
    });

    commentsList.innerHTML = html;
}

/**
 * Group comments by thread
 */
function groupCommentsByThread(commentsData) {
    const threads = {};

    commentsData.forEach(comment => {
        if (!comment.parent_comment_id) {
            // Root comment
            if (!threads[comment.thread_id]) {
                threads[comment.thread_id] = {
                    root: comment,
                    replies: []
                };
            } else {
                threads[comment.thread_id].root = comment;
            }
        } else {
            // Reply
            if (!threads[comment.thread_id]) {
                threads[comment.thread_id] = {
                    root: null,
                    replies: []
                };
            }
            threads[comment.thread_id].replies.push(comment);
        }
    });

    return Object.values(threads).filter(t => t.root !== null);
}

/**
 * Render comment thread
 */
function renderThread(thread) {
    let html = renderComment(thread.root, 0);

    // Render replies
    if (thread.replies && thread.replies.length > 0) {
        thread.replies.forEach(reply => {
            html += renderComment(reply, 1);
        });
    }

    return html;
}

/**
 * Render individual comment
 */
function renderComment(comment, depth = 0) {
    const date = new Date(comment.created_at);
    const timeAgo = getTimeAgo(date);
    const isEdited = comment.created_at !== comment.updated_at;

    // Parse mentions
    const contentWithMentions = parseMentions(comment.content);

    // Reactions
    const reactionsHtml = renderReactions(comment.id, comment.reactions || {});

    return `
        <div class="comment-item" data-comment-id="${comment.id}" style="margin-left: ${depth * 30}px;">
            <div class="comment-header">
                <div class="comment-author">
                    <i class="fas fa-user-circle me-1"></i>
                    <strong>${comment.author}</strong>
                </div>
                <div class="comment-meta">
                    <span class="comment-time" title="${date.toLocaleString()}">${timeAgo}</span>
                    ${isEdited ? '<span class="badge bg-secondary ms-1">Edited</span>' : ''}
                </div>
            </div>
            <div class="comment-content">
                ${contentWithMentions}
            </div>
            <div class="comment-actions">
                ${reactionsHtml}
                <button class="btn btn-sm btn-link text-muted" onclick="replyToComment('${comment.id}', '${comment.author}')">
                    <i class="fas fa-reply me-1"></i>Reply
                </button>
                <button class="btn btn-sm btn-link text-muted" onclick="showReactionPicker('${comment.id}')">
                    <i class="fas fa-smile me-1"></i>React
                </button>
                <div class="dropdown d-inline">
                    <button class="btn btn-sm btn-link text-muted" data-bs-toggle="dropdown">
                        <i class="fas fa-ellipsis-v"></i>
                    </button>
                    <ul class="dropdown-menu dropdown-menu-end">
                        <li><a class="dropdown-item" href="#" onclick="editComment('${comment.id}')"><i class="fas fa-edit me-2"></i>Edit</a></li>
                        <li><a class="dropdown-item text-danger" href="#" onclick="deleteComment('${comment.id}')"><i class="fas fa-trash me-2"></i>Delete</a></li>
                    </ul>
                </div>
            </div>
        </div>
    `;
}

/**
 * Parse @mentions in content
 */
function parseMentions(content) {
    return content.replace(/@(\w+)/g, '<span class="mention">@$1</span>');
}

/**
 * Render reactions
 */
function renderReactions(commentId, reactions) {
    if (!reactions || Object.keys(reactions).length === 0) {
        return '';
    }

    let html = '<div class="comment-reactions">';
    const reactionIcons = {
        'thumbs_up': '👍',
        'heart': '❤️',
        'laugh': '😂',
        'thinking': '🤔',
        'rocket': '🚀'
    };

    for (const [type, count] of Object.entries(reactions)) {
        const icon = reactionIcons[type] || '👍';
        html += `
            <span class="reaction-badge" onclick="addReaction('${commentId}', '${type}')">
                ${icon} ${count}
            </span>
        `;
    }

    html += '</div>';
    return html;
}

/**
 * Add new comment
 */
function addComment() {
    const input = document.getElementById('newCommentInput');
    const content = input.value.trim();

    if (!content) {
        return;
    }

    const widgetId = window.currentWidgetId || 'widget_demo';

    const payload = {
        content: content
    };

    if (replyingTo) {
        payload.parent_comment_id = replyingTo;
    }

    fetch(`/api/widgets/${widgetId}/comments`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Clear input
            input.value = '';
            replyingTo = null;
            updateReplyingTo(null);

            // Add comment to list
            comments.unshift(data.comment);
            renderComments(comments);
            updateCommentCount(comments.length);

            // Scroll to new comment
            scrollToComment(data.comment.id);
        } else {
            alert('Error adding comment: ' + data.message);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error adding comment');
    });
}

/**
 * Reply to comment
 */
function replyToComment(commentId, author) {
    replyingTo = commentId;
    updateReplyingTo(author);

    const input = document.getElementById('newCommentInput');
    input.focus();
}

/**
 * Update replying to UI
 */
function updateReplyingTo(author) {
    const input = document.getElementById('newCommentInput');

    if (author) {
        input.placeholder = `Replying to @${author}...`;
        input.classList.add('replying');
    } else {
        input.placeholder = 'Add a comment or use @mention...';
        input.classList.remove('replying');
    }
}

/**
 * Edit comment
 */
function editComment(commentId) {
    const comment = comments.find(c => c.id === commentId);
    if (!comment) return;

    const newContent = prompt('Edit comment:', comment.content);
    if (!newContent || newContent === comment.content) return;

    const widgetId = window.currentWidgetId || 'widget_demo';

    fetch(`/api/widgets/${widgetId}/comments/${commentId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: newContent })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Update local comment
            comment.content = newContent;
            comment.updated_at = data.comment.updated_at;
            renderComments(comments);
        } else {
            alert('Error updating comment: ' + data.message);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error updating comment');
    });
}

/**
 * Delete comment
 */
function deleteComment(commentId) {
    if (!confirm('Are you sure you want to delete this comment?')) {
        return;
    }

    const widgetId = window.currentWidgetId || 'widget_demo';

    fetch(`/api/widgets/${widgetId}/comments/${commentId}`, {
        method: 'DELETE'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Remove from list
            comments = comments.filter(c => c.id !== commentId);
            renderComments(comments);
            updateCommentCount(comments.length);
        } else {
            alert('Error deleting comment: ' + data.message);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error deleting comment');
    });
}

/**
 * Add reaction
 */
function addReaction(commentId, reactionType) {
    const widgetId = window.currentWidgetId || 'widget_demo';

    fetch(`/api/widgets/${widgetId}/comments/${commentId}/react`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reaction_type: reactionType })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Update local comment reactions
            const comment = comments.find(c => c.id === commentId);
            if (comment) {
                comment.reactions = data.comment.reactions;
                renderComments(comments);
            }
        } else {
            alert('Error adding reaction');
        }
    })
    .catch(error => {
        console.error('Error:', error);
    });
}

/**
 * Show reaction picker
 */
function showReactionPicker(commentId) {
    const reactions = [
        { type: 'thumbs_up', icon: '👍', label: 'Thumbs Up' },
        { type: 'heart', icon: '❤️', label: 'Heart' },
        { type: 'laugh', icon: '😂', label: 'Laugh' },
        { type: 'thinking', icon: '🤔', label: 'Thinking' },
        { type: 'rocket', icon: '🚀', label: 'Rocket' }
    ];

    let html = '<div class="reaction-picker">';
    reactions.forEach(r => {
        html += `
            <button class="btn btn-sm btn-light" onclick="addReaction('${commentId}', '${r.type}')" title="${r.label}">
                ${r.icon}
            </button>
        `;
    });
    html += '</div>';

    // Show in a popover or modal (simplified version)
    const picker = document.createElement('div');
    picker.className = 'reaction-picker-overlay';
    picker.innerHTML = html;
    document.body.appendChild(picker);

    // Remove on click outside
    setTimeout(() => {
        picker.addEventListener('click', function() {
            this.remove();
        });
    }, 100);
}

/**
 * Setup @mention autocomplete
 */
function setupMentionAutocomplete() {
    const input = document.getElementById('newCommentInput');
    const suggestions = document.getElementById('mentionSuggestions');

    input.addEventListener('input', function(e) {
        const value = this.value;
        const cursorPos = this.selectionStart;

        // Find @ symbol before cursor
        const textBeforeCursor = value.substring(0, cursorPos);
        const lastAtIndex = textBeforeCursor.lastIndexOf('@');

        if (lastAtIndex !== -1) {
            const queryAfterAt = textBeforeCursor.substring(lastAtIndex + 1);

            // Check if there's a space after @
            if (queryAfterAt.indexOf(' ') === -1) {
                // Filter users
                const filtered = users.filter(u => u.toLowerCase().startsWith(queryAfterAt.toLowerCase()));

                if (filtered.length > 0) {
                    showMentionSuggestions(filtered, lastAtIndex);
                    return;
                }
            }
        }

        hideMentionSuggestions();
    });

    // Handle arrow keys and enter for suggestions
    input.addEventListener('keydown', function(e) {
        if (suggestions.style.display === 'block') {
            if (e.key === 'ArrowDown' || e.key === 'ArrowUp' || e.key === 'Enter') {
                handleSuggestionNavigation(e);
            }
        }
    });
}

/**
 * Show mention suggestions
 */
function showMentionSuggestions(filteredUsers, atIndex) {
    const suggestions = document.getElementById('mentionSuggestions');
    let html = '';

    filteredUsers.slice(0, 5).forEach((user, index) => {
        html += `
            <div class="mention-suggestion-item ${index === 0 ? 'active' : ''}" data-user="${user}">
                <i class="fas fa-user-circle me-2"></i>${user}
            </div>
        `;
    });

    suggestions.innerHTML = html;
    suggestions.style.display = 'block';

    // Add click handlers
    suggestions.querySelectorAll('.mention-suggestion-item').forEach(item => {
        item.addEventListener('click', function() {
            selectMention(this.dataset.user, atIndex);
        });
    });
}

/**
 * Hide mention suggestions
 */
function hideMentionSuggestions() {
    document.getElementById('mentionSuggestions').style.display = 'none';
}

/**
 * Select mention
 */
function selectMention(username, atIndex) {
    const input = document.getElementById('newCommentInput');
    const value = input.value;

    // Replace from @ to cursor with username
    const before = value.substring(0, atIndex);
    const after = value.substring(input.selectionStart);
    input.value = before + '@' + username + ' ' + after;

    // Set cursor position
    const newPos = (before + '@' + username + ' ').length;
    input.setSelectionRange(newPos, newPos);
    input.focus();

    hideMentionSuggestions();
}

/**
 * Handle suggestion navigation
 */
function handleSuggestionNavigation(e) {
    e.preventDefault();
    const suggestions = document.getElementById('mentionSuggestions');
    const items = suggestions.querySelectorAll('.mention-suggestion-item');
    let activeIndex = Array.from(items).findIndex(i => i.classList.contains('active'));

    if (e.key === 'ArrowDown') {
        activeIndex = (activeIndex + 1) % items.length;
    } else if (e.key === 'ArrowUp') {
        activeIndex = (activeIndex - 1 + items.length) % items.length;
    } else if (e.key === 'Enter') {
        const active = items[activeIndex];
        if (active) {
            const input = document.getElementById('newCommentInput');
            const value = input.value;
            const lastAtIndex = value.lastIndexOf('@', input.selectionStart - 1);
            selectMention(active.dataset.user, lastAtIndex);
        }
        return;
    }

    items.forEach((item, idx) => {
        item.classList.toggle('active', idx === activeIndex);
    });
}

/**
 * Connect WebSocket for real-time comment updates
 */
function connectCommentWebSocket() {
    if (typeof io === 'undefined') return;

    const socket = io();

    socket.on('comment:new', function(data) {
        if (data.widget_id === window.currentWidgetId) {
            // Add new comment to list
            comments.unshift(data.comment);
            renderComments(comments);
            updateCommentCount(comments.length);

            // Show notification
            showCommentNotification('New comment from ' + data.comment.author);
        }
    });

    socket.on('comment:mention', function(data) {
        // Show mention notification
        showCommentNotification('You were mentioned by ' + data.comment.author);
    });
}

/**
 * Update comment count badge
 */
function updateCommentCount(count) {
    document.getElementById('commentCountBadge').textContent = count;
}

/**
 * Scroll to comment
 */
function scrollToComment(commentId) {
    setTimeout(() => {
        const element = document.querySelector(`[data-comment-id="${commentId}"]`);
        if (element) {
            element.scrollIntoView({ behavior: 'smooth', block: 'center' });
            element.classList.add('highlight');
            setTimeout(() => element.classList.remove('highlight'), 2000);
        }
    }, 100);
}

/**
 * Show comment notification
 */
function showCommentNotification(message) {
    // Simple notification - can be replaced with toast library
    if (Notification.permission === 'granted') {
        new Notification('Claude Monitoring', { body: message });
    }
}

/**
 * Get time ago string
 */
function getTimeAgo(date) {
    const seconds = Math.floor((new Date() - date) / 1000);

    const intervals = {
        year: 31536000,
        month: 2592000,
        week: 604800,
        day: 86400,
        hour: 3600,
        minute: 60
    };

    for (const [unit, secondsInUnit] of Object.entries(intervals)) {
        const interval = Math.floor(seconds / secondsInUnit);
        if (interval >= 1) {
            return interval === 1 ? `1 ${unit} ago` : `${interval} ${unit}s ago`;
        }
    }

    return 'just now';
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('commentsList')) {
        initializeComments();
    }
});
