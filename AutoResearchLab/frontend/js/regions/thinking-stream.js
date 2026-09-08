(function () {
    'use strict';
    window.MAARS = window.MAARS || {};

    function appendThinkingChunk(state, prefix, chunk, taskId, operation, scheduleInfo, source, scheduleRender) {
        const blocksKey = `${prefix}ThinkingBlocks`;
        const planStreamingKey = `${prefix}PlanStreamingKey`;
        const ideaStreamingKey = `${prefix}IdeaStreamingKey`;
        const paperStreamingKey = `${prefix}PaperStreamingKey`;
        const scheduleCounterKey = `${prefix}ScheduleCounter`;
        const planCounterKey = `${prefix}PlanCounter`;
        const ideaCounterKey = `${prefix}IdeaCounter`;
        const lastUpdatedKey = `${prefix}LastUpdatedBlockKey`;
        const isIdea = source === 'idea' || operation === 'Refine';
        const isPaper = source === 'paper' || operation === 'Paper';

        if (!chunk && scheduleInfo != null) {
            state[planStreamingKey] = '';
            state[ideaStreamingKey] = '';
            if (scheduleInfo.tool_name || scheduleInfo.operation) {
                state[scheduleCounterKey] = (state[scheduleCounterKey] || 0) + 1;
                const key = `schedule_${state[scheduleCounterKey]}`;
                state[blocksKey].push({
                    key,
                    blockType: 'schedule',
                    scheduleInfo,
                    taskId: taskId ?? scheduleInfo.task_id,
                    operation: operation ?? scheduleInfo.operation,
                    source: source || 'task',
                });
                state[lastUpdatedKey] = key;
                scheduleRender();
            }
            return;
        }

        if (taskId == null && isPaper && chunk) {
            const paperCounterKey = `${prefix}PaperCounter`;
            let block = state[paperStreamingKey] ? state[blocksKey].find((b) => b.key === state[paperStreamingKey]) : null;
            state[planStreamingKey] = '';
            state[ideaStreamingKey] = '';
            if (block) {
                block.content += chunk;
                if (scheduleInfo != null) block.scheduleInfo = scheduleInfo;
                state[lastUpdatedKey] = block.key;
            } else {
                state[paperCounterKey] = (state[paperCounterKey] || 0) + 1;
                const key = `paper_${state[paperCounterKey]}`;
                block = { key, taskId: null, operation: operation || 'Paper', content: chunk, scheduleInfo: scheduleInfo || null, source: 'paper' };
                state[blocksKey].push(block);
                state[paperStreamingKey] = key;
                state[lastUpdatedKey] = key;
            }
            scheduleRender();
            return;
        }

        if (taskId == null && isIdea && chunk) {
            let block = state[ideaStreamingKey] ? state[blocksKey].find((b) => b.key === state[ideaStreamingKey]) : null;
            state[planStreamingKey] = '';
            state[paperStreamingKey] = '';
            if (block && block.operation !== operation) {
                block = null;
                state[ideaStreamingKey] = '';
            }
            if (block) {
                block.content += chunk;
                if (scheduleInfo != null) block.scheduleInfo = scheduleInfo;
                state[lastUpdatedKey] = block.key;
            } else {
                state[ideaCounterKey] = (state[ideaCounterKey] || 0) + 1;
                const key = `idea_${state[ideaCounterKey]}`;
                block = { key, taskId: null, operation: operation || 'Refine', content: chunk, scheduleInfo: scheduleInfo || null, source: 'idea' };
                state[blocksKey].push(block);
                state[ideaStreamingKey] = key;
                state[lastUpdatedKey] = key;
            }
            scheduleRender();
            return;
        }

        if (taskId == null && chunk) {
            let block = state[planStreamingKey] ? state[blocksKey].find((b) => b.key === state[planStreamingKey]) : null;
            state[ideaStreamingKey] = '';
            state[paperStreamingKey] = '';
            if (block && block.operation !== operation) {
                block = null;
                state[planStreamingKey] = '';
            }
            if (block) {
                block.content += chunk;
                if (scheduleInfo != null) block.scheduleInfo = scheduleInfo;
                state[lastUpdatedKey] = block.key;
            } else {
                state[planCounterKey] = (state[planCounterKey] || 0) + 1;
                const key = `plan_${state[planCounterKey]}`;
                block = { key, taskId: null, operation: operation || 'Plan', content: chunk, scheduleInfo: scheduleInfo || null, source: 'plan' };
                state[blocksKey].push(block);
                state[planStreamingKey] = key;
                state[lastUpdatedKey] = key;
            }
            scheduleRender();
            return;
        }

        state[planStreamingKey] = '';
        state[ideaStreamingKey] = '';
        state[paperStreamingKey] = '';
        const key = (taskId != null && operation != null) ? `${String(taskId)}::${String(operation)}` : '_default';
        let block = state[blocksKey].find((b) => b.key === key);
        if (!block) {
            block = { key, taskId, operation, content: '', scheduleInfo: null, source: source || 'task' };
            state[blocksKey].push(block);
        }
        if (chunk) block.content += chunk;
        if (scheduleInfo != null) block.scheduleInfo = scheduleInfo;
        state[lastUpdatedKey] = key;
        scheduleRender();
    }

    window.MAARS.appendThinkingChunk = appendThinkingChunk;
})();
