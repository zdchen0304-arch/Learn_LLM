/**
 * MAARS Output region helpers.
 * Pure formatting/serialization helpers used by output.js.
 */
(function () {
    'use strict';

    function sortOutputKeys(outputs) {
        return Object.keys(outputs || {}).sort((a, b) => {
            if (a === 'idea') return -1;
            if (b === 'idea') return 1;
            if (a === 'paper') return 1;
            if (b === 'paper') return -1;
            if (a.startsWith('task_') && b.startsWith('task_')) {
                const na = parseInt(a.slice(6), 10);
                const nb = parseInt(b.slice(6), 10);
                if (!isNaN(na) && !isNaN(nb)) return na - nb;
            }
            return String(a).localeCompare(b);
        });
    }

    function formatRefineResult(data) {
        const source = data || {};
        const keywords = source.keywords || [];
        const papers = source.papers || [];
        const refined = (typeof source.refined_idea === 'string') ? source.refined_idea.trim() : '';

        let md = '## Refine Results\n\n';
        if (refined) md += `### Refined Idea\n\n${refined}\n\n`;
        md += `**Keywords:** ${keywords.length ? keywords.join(', ') : '—'}\n\n`;
        md += `**Papers (${papers.length}):**\n\n`;
        papers.forEach((paper, index) => {
            const title = String(paper?.title || '').replace(/[[\]]/g, '\\$&');
            const url = paper?.url || '#';
            const authors = Array.isArray(paper?.authors) ? paper.authors.join(', ') : '';
            const published = String(paper?.published || '').trim();
            const abstractRaw = String(paper?.abstract || '').replace(/\s+/g, ' ').trim();
            const abstract = abstractRaw.slice(0, 300) + (abstractRaw.length > 300 ? '...' : '');

            md += `${index + 1}. **[${title}](${url})**`;
            if (published) md += ` (${published})`;
            md += '\n';
            if (authors) md += `   *Authors:* ${authors}\n`;
            if (abstract) md += `   ${abstract}\n`;
            md += '\n';
        });
        return md;
    }

    function renderContent(raw, markedRef) {
        let displayLabel = '';
        let html = '';

        if (typeof raw === 'object' && raw !== null && raw.label) {
            displayLabel = raw.label;
            if ('content' in raw && typeof raw.content === 'string') {
                const text = raw.content || '';
                html = text ? (typeof markedRef !== 'undefined' ? markedRef.parse(text) : text) : '';
            } else {
                const str = JSON.stringify(raw, null, 2);
                html = typeof markedRef !== 'undefined'
                    ? markedRef.parse(`\`\`\`json\n${str}\n\`\`\``)
                    : `<pre>${str}</pre>`;
            }
        } else {
            html = (raw || '') ? (typeof markedRef !== 'undefined' ? markedRef.parse(String(raw)) : String(raw)) : '';
        }

        return {
            displayLabel: String(displayLabel || '').trim(),
            html: html || '',
        };
    }

    function normalizeLabel(taskId, renderedLabel) {
        if (renderedLabel) return renderedLabel;
        if (taskId === 'idea') return 'Refine';
        if (String(taskId || '').startsWith('task_')) return `Task ${String(taskId).slice(6)}`;
        return `Task ${taskId || ''}`;
    }

    function toDownloadPayload(raw, taskId) {
        let text = '';
        let ext = 'txt';
        if (raw != null) {
            if (typeof raw === 'string') {
                text = raw;
                ext = 'md';
            } else if (typeof raw === 'object' && raw !== null && 'content' in raw && typeof raw.content === 'string') {
                text = raw.content;
                ext = 'md';
            } else {
                text = JSON.stringify(raw, null, 2);
                ext = 'json';
            }
        }
        const safeId = String(taskId || 'output').replace(/[^a-zA-Z0-9_-]/g, '_');
        return {
            text,
            ext,
            filename: `task-${safeId}.${ext}`,
            mime: ext === 'json' ? 'application/json' : 'text/markdown',
        };
    }

    window.MAARS = window.MAARS || {};
    window.MAARS.outputUtils = {
        sortOutputKeys,
        formatRefineResult,
        renderContent,
        normalizeLabel,
        toDownloadPayload,
    };
})();
