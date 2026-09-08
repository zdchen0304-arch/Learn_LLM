(function () {
    'use strict';
    window.MAARS = window.MAARS || {};

    function bindTaskTreeEvents(deps) {
        const AREA = deps?.AREA;
        const clear = deps?.clear;
        const renderPlanAgentTree = deps?.renderPlanAgentTree;
        const updatePlanAgentQualityBadge = deps?.updatePlanAgentQualityBadge;
        const updateTaskStates = deps?.updateTaskStates;

        const onFlowStart = () => {
            clear(AREA.decomposition);
            updatePlanAgentQualityBadge(null);
        };
        document.addEventListener('maars:idea-start', onFlowStart);
        document.addEventListener('maars:plan-start', onFlowStart);

        document.addEventListener('maars:plan-tree-update', (e) => {
            const { treeData, layout } = e.detail || {};
            if (treeData) renderPlanAgentTree(treeData, layout);
        });

        document.addEventListener('maars:plan-complete', (e) => {
            const data = e.detail || {};
            if (data.treeData) renderPlanAgentTree(data.treeData, data.layout);
            updatePlanAgentQualityBadge(data.qualityScore, data.qualityComment);
        });

        document.addEventListener('maars:task-states-update', (e) => {
            const data = e.detail;
            if (data?.tasks && Array.isArray(data.tasks)) updateTaskStates(data.tasks);
        });

        document.addEventListener('maars:execution-sync', (e) => {
            const data = e.detail;
            if (data?.tasks && Array.isArray(data.tasks)) updateTaskStates(data.tasks);
        });

        document.addEventListener('maars:restore-complete', (e) => {
            const { treePayload, plan, execution } = e.detail || {};
            if (treePayload?.treeData?.length) {
                renderPlanAgentTree(treePayload.treeData, treePayload.layout);
                if (plan?.qualityScore != null) updatePlanAgentQualityBadge(plan.qualityScore, plan.qualityComment);
            }

            const snapshotTasks = Array.isArray(execution?.tasks) ? execution.tasks : [];
            if (snapshotTasks.length) {
                updateTaskStates(snapshotTasks.map((t) => ({
                    task_id: t?.task_id,
                    status: t?.status || 'undone',
                })).filter((t) => t.task_id));
            }
        });
    }

    window.MAARS.bindTaskTreeEvents = bindTaskTreeEvents;
})();
