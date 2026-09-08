/**
 * MAARS research execute utility helpers.
 * Keeps pure formatting/reduction logic out of research.js orchestration flow.
 */
(function () {
    'use strict';

    function stringifyOutput(val) {
        if (val == null) return '';
        if (typeof val === 'string') return val;
        try {
            if (typeof val === 'object' && val !== null && 'content' in val && typeof val.content === 'string') return val.content;
        } catch (_) { }
        try {
            return JSON.stringify(val, null, 2);
        } catch (_) {
            return String(val);
        }
    }

    function statusLabel(status) {
        const s = String(status || '').trim() || 'undone';
        const map = {
            undone: 'Pending',
            doing: 'Running',
            done: 'Done',
            'execution-failed': 'Execution Failed',
            'validation-failed': 'Validation Failed',
        };
        return map[s] || s;
    }

    function statusTone(status) {
        const s = String(status || '').trim();
        if (s === 'doing') return 'doing';
        if (s === 'done') return 'done';
        if (s === 'execution-failed' || s === 'validation-failed') return 'failed';
        return 'pending';
    }

    function extractValidationDirectReason(reportText) {
        const text = String(reportText || '').trim();
        if (!text) return 'Validation gate failed.';

        const lines = text.split('\n').map((line) => line.trim()).filter(Boolean);
        const markerLine = lines.find((line) => /^DIRECT_REASON:/i.test(line));
        if (markerLine) return markerLine.replace(/^DIRECT_REASON:\s*/i, '').trim() || 'Validation gate failed.';

        const parenFailLine = lines.find((line) => !line.startsWith('#') && /FAIL\s*\(/i.test(line));
        if (parenFailLine) return parenFailLine.replace(/^[-*]\s*/, '');
        const failLine = lines.find((line) => !line.startsWith('#') && /failed|fail/i.test(line));
        if (failLine) return failLine.replace(/^[-*]\s*/, '');
        const firstMeaningful = lines.find((line) => !line.startsWith('#'));
        return firstMeaningful || lines[0] || 'Validation gate failed.';
    }

    function buildValidationSummaryBody(options = {}) {
        const taskId = String(options.taskId || '').trim();
        const detail = options.detail || {};
        const meta = options.meta || {};
        const status = String(options.statusLabel || 'FAILED').trim() || 'FAILED';
        const latestStepBByTask = options.latestStepBByTask;

        const fallbackError = String(detail?.error || '').trim();
        const summary = detail?.validationSummary || detail?.decision?.validationSummary || {};
        const decisionStepB = detail?.decision?.stepB || {};
        const summaryStepB = summary?.stepB || {};
        const fallbackStepB = (latestStepBByTask && typeof latestStepBByTask.get === 'function')
            ? (latestStepBByTask.get(taskId) || {})
            : {};
        const stepB = (summaryStepB && Object.keys(summaryStepB).length)
            ? summaryStepB
            : ((decisionStepB && Object.keys(decisionStepB).length) ? decisionStepB : fallbackStepB);

        const shouldAdjust = stepB?.shouldAdjust === true;
        const immutableImpacted = stepB?.immutableImpacted === true;
        const patchSummary = String(stepB?.patchSummary || '').trim();
        const reasoning = String(stepB?.reasoning || '').trim();

        const expectedFormat = String(summary?.expectedFormat || meta?.outputFormat || '').trim() || 'unknown';
        const finalCheckRaw = String(summary?.finalCheckResult || fallbackError).trim();
        const finalCheck = finalCheckRaw
            .split('\n')
            .map((line) => line.trim())
            .filter(Boolean)
            .slice(0, 10)
            .join('\n');

        const directReasonRaw = String(summary?.directReason || '').trim();
        const directReason = directReasonRaw || extractValidationDirectReason(finalCheckRaw || fallbackError);

        const parts = [];
        parts.push(`Final check result (${status}):\n${finalCheck || 'Validation report unavailable.'}`);
        parts.push(`Expected format: ${expectedFormat}`);
        parts.push(`Contract update by agent: ${shouldAdjust ? 'Adjusted mutable criteria' : 'No change'}${immutableImpacted ? ' (blocked by immutable constraints)' : ''}`);
        if (patchSummary) parts.push(`Step B patch: ${patchSummary}`);
        if (reasoning) parts.push(`Step B reasoning: ${reasoning}`);
        parts.push(`Direct reason: ${directReason}`);
        return parts.join('\n\n');
    }

    function formatElapsedDuration(ms) {
        const totalSeconds = Math.max(0, Math.floor((Number(ms) || 0) / 1000));
        const hours = Math.floor(totalSeconds / 3600);
        const minutes = Math.floor((totalSeconds % 3600) / 60);
        const seconds = totalSeconds % 60;
        if (hours > 0) return `${hours}h ${minutes}m ${seconds}s`;
        if (minutes > 0) return `${minutes}m ${seconds}s`;
        return `${seconds}s`;
    }

    function getAttemptKey(taskId, attempt) {
        return `${String(taskId || '').trim()}:${Number(attempt) || 1}`;
    }

    function getAttemptStatus(options = {}) {
        const list = Array.isArray(options.msgs) ? options.msgs : [];
        if (list.some((m) => m.status === 'done')) return 'done';
        if (list.some((m) => m.status === 'validation-failed')) return 'validation-failed';
        if (list.some((m) => m.status === 'execution-failed')) return 'execution-failed';
        if (list.some((m) => m.kind === 'error')) return 'validation-failed';

        const currentAttempt = Number(options.currentAttempt) || 1;
        if (Number(options.attempt) < currentAttempt) return 'validation-failed';

        return String(options.fallbackStatus || 'doing').trim() || 'doing';
    }

    function getAttemptSummary(msgs) {
        const list = Array.isArray(msgs) ? msgs : [];
        for (let i = list.length - 1; i >= 0; i--) {
            const m = list[i];
            if (m.kind === 'error' || m.kind === 'system') {
                const body = String(m.body || '');
                const match = body.match(/^Direct reason:\s*(.+)/im);
                if (match && match[1].trim()) {
                    const reason = match[1].trim();
                    return reason.length > 180 ? `${reason.slice(0, 180)}...` : reason;
                }
            }
        }

        const source = [...list].reverse().find((m) => m.kind === 'error' || (m.kind === 'system' && /retry|failed|error/i.test(String(m.title || ''))))
            || list[list.length - 1];
        const text = String(source?.body || '').trim();
        if (!text) return '';
        const firstLine = text.split('\n').map((line) => line.trim()).filter(Boolean)[0] || text;
        return firstLine.length > 180 ? `${firstLine.slice(0, 180)}...` : firstLine;
    }

    function replayPersistedStepEvents(stepEvents) {
        const events = Array.isArray(stepEvents?.events) ? stepEvents.events : [];
        if (!events.length) return;

        const eventMap = {
            'task-started': 'maars:task-started',
            'task-thinking': 'maars:task-thinking',
            'task-output': 'maars:task-output',
            'task-step-b': 'maars:task-step-b',
            'task-error': 'maars:task-error',
            'attempt-retry': 'maars:attempt-retry',
            'task-retry': 'maars:attempt-retry',
            'task-completed': 'maars:task-completed',
            'task-complete': 'maars:task-complete',
        };

        events.forEach((item) => {
            const name = String(item?.event || '').trim();
            const domEvent = eventMap[name];
            if (!domEvent) return;
            const payload = item && typeof item.payload === 'object' && item.payload !== null ? item.payload : {};
            const taskId = String(item?.taskId || '').trim();
            const detail = taskId
                ? { ...payload, taskId, __replayed: true }
                : { ...payload, __replayed: true };
            document.dispatchEvent(new CustomEvent(domEvent, { detail }));
        });
    }

    function buildRuntimeStatusViewModel(status) {
        const next = status && typeof status === 'object' ? status : {};
        const enabled = !!next.enabled;
        const connected = !!next.connected;
        const containerRunning = !!next.containerRunning;
        const running = !!next.running;

        let badgeText = 'Docker: checking...';
        let tone = 'is-warn';
        if (!enabled) {
            badgeText = 'Docker: disabled';
            tone = 'is-warn';
        } else if (!next.available) {
            badgeText = 'Docker: not found';
            tone = 'is-error';
        } else if (!connected) {
            badgeText = 'Docker: disconnected';
            tone = 'is-error';
        } else if (containerRunning && running) {
            badgeText = 'Docker: running';
            tone = 'is-ok';
        } else if (containerRunning) {
            badgeText = 'Docker: connected';
            tone = 'is-ok';
        } else {
            badgeText = 'Docker: ready';
            tone = 'is-warn';
        }

        const shortMetaParts = [];
        const detailParts = [];
        const imageText = String(next.image || '').trim();
        const shortImage = imageText ? imageText.split('/').pop() : '';

        if (next.serverVersion) shortMetaParts.push(`Engine ${next.serverVersion}`);
        if (shortImage) shortMetaParts.push(`Image ${shortImage}`);
        if (next.executionRunId) shortMetaParts.push(`Run ${next.executionRunId}`);
        if (next.executionRunId) shortMetaParts.push('Step per task');
        if (next.error) shortMetaParts.push('Error');
        if (!shortMetaParts.length && !enabled) shortMetaParts.push('Enable Docker-backed execution in Task Agent mode.');

        if (next.serverVersion) detailParts.push(`Engine ${next.serverVersion}`);
        if (imageText) detailParts.push(`Image ${imageText}`);
        if (next.volumeName) detailParts.push(`Volume ${next.volumeName}`);
        if (next.executionRunId) detailParts.push(`Run ${next.executionRunId}`);
        if (next.srcDir) detailParts.push(`Src ${next.srcDir}`);
        if (next.stepDir) detailParts.push(`Step ${next.stepDir}`);
        else if (next.executionRunId) detailParts.push('Step per task');
        if (next.error) detailParts.push(String(next.error).trim());

        return {
            badgeText,
            tone,
            shortMetaText: shortMetaParts.join(' · '),
            detailMetaText: detailParts.join('\n'),
        };
    }

    window.MAARS = window.MAARS || {};
    window.MAARS.researchExecuteUtils = {
        stringifyOutput,
        statusLabel,
        statusTone,
        extractValidationDirectReason,
        buildValidationSummaryBody,
        formatElapsedDuration,
        getAttemptKey,
        getAttemptStatus,
        getAttemptSummary,
        replayPersistedStepEvents,
        buildRuntimeStatusViewModel,
    };
})();
