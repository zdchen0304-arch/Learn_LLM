(function () {
    'use strict';
    window.MAARS = window.MAARS || {};

    function createTaskTreePopoverController(deps) {
        const deriveDisplayTitle = deps?.deriveDisplayTitle || ((task) => String(task?.task_id || 'Task'));
        const escapeHtml = deps?.escapeHtml || ((s) => String(s ?? ''));

        let popoverEl = null;
        let popoverAnchor = null;
        let popoverOutsideClickHandler = null;
        let popoverKeydownHandler = null;

        function buildTaskDetailBody(task) {
            const title = deriveDisplayTitle(task);
            const desc = (task.description || task.objective || '').trim() || '-';
            const depsText = (task.dependencies || []).length > 0 ? (task.dependencies || []).join(', ') : 'None';
            const hasStatus = task.status != null;
            const isFailed = task.status === 'execution-failed' || task.status === 'validation-failed';
            const isUndone = !task.status || task.status === 'undone';
            const statusRow = hasStatus ? `<div class="task-detail-row"><span class="task-detail-label">Status:</span><span class="task-detail-value task-status-${task.status}">${escapeHtml(task.status)}</span></div>` : '';
            const actionRow = isFailed
                ? `<div class="task-detail-row task-detail-actions"><button type="button" class="btn-default task-retry-btn" data-retry-task-id="${escapeHtml(task.task_id)}">Retry</button></div>`
                : isUndone
                    ? `<div class="task-detail-row task-detail-actions"><button type="button" class="btn-default task-resume-btn" data-resume-task-id="${escapeHtml(task.task_id)}">Run from here</button></div>`
                    : '';
            const hasInputOutput = task.input && task.output;
            const inputRow = hasInputOutput ? `<div class="task-detail-row"><span class="task-detail-label">Input:</span><span class="task-detail-value">${escapeHtml(task.input.description || '-')}</span></div>` : '';
            const out = task.output || {};
            const outputDesc = hasInputOutput ? [out.artifact || out.description, out.format].filter(Boolean).join(' · ') || '-' : '-';
            const outputRow = hasInputOutput ? `<div class="task-detail-row"><span class="task-detail-label">Output:</span><span class="task-detail-value">${escapeHtml(outputDesc)}</span></div>` : '';
            const v = task.validation;
            const hasValidation = v && (v.description || (Array.isArray(v.criteria) && v.criteria.length > 0));
            const validationRow = hasValidation ? (() => {
                const vdesc = v.description ? `<div class="validation-desc">${escapeHtml(v.description)}</div>` : '';
                const criteriaList = (v.criteria || []).map(c => `<li>${escapeHtml(c)}</li>`).join('');
                const criteriaHtml = criteriaList ? `<ul class="validation-criteria">${criteriaList}</ul>` : '';
                const optionalList = (v.optionalChecks || []).map(c => `<li>${escapeHtml(c)}</li>`).join('');
                const optionalHtml = optionalList ? `<ul class="validation-optional">${optionalList}</ul>` : '';
                return `<div class="task-detail-row task-detail-validation"><span class="task-detail-label">Validation:</span><div class="task-detail-value">${vdesc}${criteriaHtml}${optionalHtml}</div></div>`;
            })() : '';
            return `<div class="task-detail-row"><span class="task-detail-label">Title:</span><span class="task-detail-value">${escapeHtml(title)}</span></div>
                <div class="task-detail-row"><span class="task-detail-label">Description:</span><span class="task-detail-value">${escapeHtml(desc)}</span></div>
                    <div class="task-detail-row"><span class="task-detail-label">Dependencies:</span><span class="task-detail-value">${escapeHtml(depsText)}</span></div>
                    ${statusRow}
                    ${inputRow}
                    ${outputRow}
                    ${validationRow}
                    ${actionRow}`;
        }

        function hideTaskPopover() {
            if (popoverOutsideClickHandler) {
                document.removeEventListener('click', popoverOutsideClickHandler);
                popoverOutsideClickHandler = null;
            }
            if (popoverKeydownHandler) {
                document.removeEventListener('keydown', popoverKeydownHandler);
                popoverKeydownHandler = null;
            }
            if (popoverEl) {
                popoverEl.remove();
                popoverEl = null;
                popoverAnchor = null;
            }
        }

        function showTaskPopover(taskOrTasks, anchorEl) {
            if (popoverEl && popoverAnchor === anchorEl) {
                hideTaskPopover();
                return;
            }
            hideTaskPopover();

            const tasks = Array.isArray(taskOrTasks) ? taskOrTasks : [taskOrTasks];
            const single = tasks.length === 1;

            popoverEl = document.createElement('div');
            popoverEl.className = 'task-detail-popover';
            popoverEl.setAttribute('role', 'dialog');
            popoverEl.setAttribute('aria-label', 'Task details');

            if (single) {
                const task = tasks[0];
                popoverEl.innerHTML = `
                    <div class="task-detail-popover-header">
                        <span class="task-detail-popover-title">${escapeHtml(task.task_id)}</span>
                        <button class="task-detail-popover-close" aria-label="Close">&times;</button>
                    </div>
                    <div class="task-detail-popover-body">${buildTaskDetailBody(task)}</div>
                `;
            } else {
                const tabsHtml = tasks.map((t, i) => {
                    const statusClass = (t.status && t.status !== 'undone') ? ` task-status-${t.status}` : '';
                    return `<button type="button" class="task-detail-tab${statusClass}" data-tab-index="${i}" data-tab-task-id="${escapeHtml(t.task_id)}" aria-pressed="${i === 0}">${escapeHtml(t.task_id)}</button>`;
                }).join('');
                popoverEl.innerHTML = `
                    <div class="task-detail-popover-header task-detail-popover-header-tabs">
                        <div class="task-detail-tabs">${tabsHtml}</div>
                        <button class="task-detail-popover-close" aria-label="Close">&times;</button>
                    </div>
                    <div class="task-detail-popover-body">${buildTaskDetailBody(tasks[0])}</div>
                `;
                const tabs = popoverEl.querySelectorAll('.task-detail-tab');
                const body = popoverEl.querySelector('.task-detail-popover-body');
                tabs.forEach((tab, i) => {
                    tab.addEventListener('click', () => {
                        tabs.forEach((t) => t.setAttribute('aria-pressed', 'false'));
                        tab.setAttribute('aria-pressed', 'true');
                        body.innerHTML = buildTaskDetailBody(tasks[i]);
                    });
                });
            }

            document.body.appendChild(popoverEl);
            popoverAnchor = anchorEl;

            const rect = anchorEl.getBoundingClientRect();
            const gap = 8;
            let left = rect.right + gap;
            let top = rect.top + rect.height / 2 - popoverEl.offsetHeight / 2;
            if (left + popoverEl.offsetWidth > window.innerWidth - 12) left = rect.left - popoverEl.offsetWidth - gap;
            if (left < 12) left = 12;
            if (top < 12) top = 12;
            if (top + popoverEl.offsetHeight > window.innerHeight - 12) top = window.innerHeight - popoverEl.offsetHeight - 12;

            popoverEl.style.left = left + 'px';
            popoverEl.style.top = top + 'px';

            popoverEl.querySelector('.task-detail-popover-close').addEventListener('click', hideTaskPopover);
            popoverEl.addEventListener('click', (e) => {
                const retryBtn = e.target.closest('.task-retry-btn');
                const resumeBtn = e.target.closest('.task-resume-btn');
                const taskId = retryBtn?.getAttribute('data-retry-task-id') || resumeBtn?.getAttribute('data-resume-task-id');
                if (taskId) {
                    document.dispatchEvent(new CustomEvent(retryBtn ? 'maars:attempt-retry-request' : 'maars:task-resume', { detail: { taskId } }));
                    hideTaskPopover();
                }
            });
            popoverOutsideClickHandler = (e) => {
                if (popoverEl && !popoverEl.contains(e.target) && !e.target.closest('.tree-task')) hideTaskPopover();
            };
            popoverKeydownHandler = (e) => {
                if (e.key === 'Escape') hideTaskPopover();
            };
            document.addEventListener('click', popoverOutsideClickHandler);
            document.addEventListener('keydown', popoverKeydownHandler);
        }

        function initClickHandlers() {
            document.addEventListener('click', (e) => {
                const node = e.target.closest('.tree-task');
                if (!node) return;
                const data = node.getAttribute('data-task-data');
                if (!data) return;
                try {
                    showTaskPopover(JSON.parse(data), node);
                    e.stopPropagation();
                } catch (_) {}
            });
        }

        return {
            hideTaskPopover,
            initClickHandlers,
            showTaskPopover,
        };
    }

    window.MAARS.createTaskTreePopoverController = createTaskTreePopoverController;
})();
