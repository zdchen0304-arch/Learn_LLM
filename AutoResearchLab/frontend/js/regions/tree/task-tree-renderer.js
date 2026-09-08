(function () {
    'use strict';
    window.MAARS = window.MAARS || {};

    function createTaskTreeRenderer(deps) {
        const AREA = deps?.AREA;
        const deriveDisplayTitle = deps?.deriveDisplayTitle || ((task) => String(task?.task_id || 'Task'));
        const getTreeContainer = deps?.getTreeContainer;
        const getZoomLevel = deps?.getZoomLevel || (() => 1.0);

        function getTaskDataForPopover(task) {
            return {
                task_id: task.task_id,
                title: task.title,
                description: task.description,
                objective: task.objective,
                dependencies: task.dependencies,
                status: task.status,
                input: task.input,
                output: task.output,
                validation: task.validation,
                task_type: task.task_type,
                inputs: task.inputs,
                outputs: task.outputs,
                target: task.target,
                timeout_seconds: task.timeout_seconds,
            };
        }

        function createTaskNodeEl(task) {
            const tid = task.task_id;
            const desc = (task.description || task.objective || '').trim() || tid || 'Task';
            const title = deriveDisplayTitle(task);

            const el = document.createElement('div');
            el.className = 'tree-task';
            el.setAttribute('data-task-id', tid);
            el.setAttribute('data-task-data', JSON.stringify(getTaskDataForPopover(task)));
            el.setAttribute('title', desc);

            const label = document.createElement('span');
            label.className = 'tree-task-label';
            label.textContent = title;
            el.appendChild(label);

            return el;
        }

        function aggregateStatus(tasks) {
            const hasError = tasks.some((t) => t?.status === 'execution-failed' || t?.status === 'validation-failed');
            const allDone = tasks.length > 0 && tasks.every((t) => t?.status === 'done');
            const allUndone = tasks.length > 0 && tasks.every((t) => !t?.status || t?.status === 'undone');
            if (hasError) return 'execution-failed';
            if (allDone) return 'done';
            if (allUndone) return 'undone';
            return 'doing';
        }

        function createMergedTaskNodeEl(taskIds, taskById) {
            const tid = taskIds[0] || '?';
            const taskDatas = taskIds.map((id) => getTaskDataForPopover(taskById.get(id) || { task_id: id }));
            const status = aggregateStatus(taskDatas);
            const desc = taskIds.join(', ');

            const el = document.createElement('div');
            el.className = 'tree-task tree-task-leaf tree-task-merged';
            if (status && status !== 'undone') el.classList.add('task-status-' + status);
            el.setAttribute('data-task-id', tid);
            el.setAttribute('data-task-ids', taskIds.join(','));
            el.setAttribute('data-task-data', JSON.stringify(taskDatas));
            el.setAttribute('title', desc);

            const badge = document.createElement('span');
            badge.className = 'tree-task-count';
            badge.textContent = String(taskIds.length);
            el.appendChild(badge);

            return el;
        }

        function buildSmoothPath(pts) {
            if (!pts || pts.length < 2) return '';
            const [x1, y1] = pts[0];
            const [x2, y2] = pts[1];
            const my = (y1 + y2) / 2;
            return `M ${x1} ${y1} C ${x1} ${my}, ${x2} ${my}, ${x2} ${y2}`;
        }

        function scaleLayout(layout, factor) {
            if (!layout || !factor || factor === 1) return layout;
            const nodes = layout.nodes || {};
            const edges = Array.isArray(layout.edges) ? layout.edges : [];

            const scaledNodes = {};
            Object.entries(nodes).forEach(([id, n]) => {
                scaledNodes[id] = {
                    ...n,
                    x: Number((n.x * factor).toFixed(1)),
                    y: Number((n.y * factor).toFixed(1)),
                    w: Number((n.w * factor).toFixed(1)),
                    h: Number((n.h * factor).toFixed(1)),
                };
            });

            const scaledEdges = edges.map((e) => ({
                ...e,
                points: (e.points || []).map((pt) => [
                    Number(((pt?.[0] || 0) * factor).toFixed(1)),
                    Number(((pt?.[1] || 0) * factor).toFixed(1)),
                ]),
            }));

            return {
                ...layout,
                nodes: scaledNodes,
                edges: scaledEdges,
                width: Number(((layout.width || 0) * factor).toFixed(1)),
                height: Number(((layout.height || 0) * factor).toFixed(1)),
            };
        }

        function calculateAdaptiveScale(treeData, baseLayout, areaSelector) {
            if (!baseLayout) return getZoomLevel();

            const ctx = getTreeContainer(areaSelector);
            if (!ctx) return getZoomLevel();

            const containerWidth = ctx.area.clientWidth || 800;
            const containerHeight = ctx.area.clientHeight || 600;
            const baseWidth = baseLayout.width || 500;
            const baseHeight = baseLayout.height || 400;

            const scaleByWidth = (containerWidth - 40) / baseWidth;
            const scaleByHeight = (containerHeight - 40) / baseHeight;
            const fitScale = Math.min(scaleByWidth, scaleByHeight, 2.0);

            let titleScale = 1.0;
            if (treeData && Array.isArray(treeData)) {
                treeData.forEach((task) => {
                    const title = deriveDisplayTitle(task) || '';
                    const isChinese = /[\u4e00-\u9fff]/.test(title);
                    const charWidth = isChinese ? 8 : 7;
                    const requiredWidth = Math.min(title.length * charWidth + 20, 350);
                    if (requiredWidth > 180) {
                        titleScale = Math.max(titleScale, requiredWidth / 180);
                    }
                });
            }

            const baseScale = Math.max(fitScale, titleScale);
            return baseScale * getZoomLevel();
        }

        function renderFull(treeData, layout, areaSelector) {
            const ctx = getTreeContainer(areaSelector);
            if (!ctx) return;

            const tasks = (treeData || []).filter((t) => t?.task_id);
            ctx.tree.innerHTML = '';
            if (tasks.length === 0 || !layout) return;

            const adaptiveScale = calculateAdaptiveScale(treeData, layout, areaSelector);
            const scaledLayout = scaleLayout(layout, adaptiveScale);
            const { nodes, edges, width, height } = scaledLayout;
            if (!nodes) return;

            ctx.tree.style.width = width + 'px';
            ctx.tree.style.height = height + 'px';
            ctx.tree.style.minHeight = height + 'px';

            const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
            svg.setAttribute('class', 'tree-connection-lines');
            svg.setAttribute('width', width);
            svg.setAttribute('height', height);
            svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
            ctx.tree.appendChild(svg);

            (edges || []).forEach((edge) => {
                const pts = edge.points;
                if (!pts || pts.length < 2) return;
                const d = buildSmoothPath(pts);
                const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
                path.setAttribute('d', d);
                path.setAttribute('stroke-width', '1.5');
                path.setAttribute('fill', 'none');
                const fromVal = edge.from;
                const toVal = edge.to;
                if (Array.isArray(fromVal)) {
                    path.setAttribute('data-from-tasks', fromVal.join(','));
                } else {
                    path.setAttribute('data-from-task', fromVal);
                }
                if (Array.isArray(toVal)) {
                    path.setAttribute('data-to-tasks', toVal.join(','));
                } else {
                    path.setAttribute('data-to-task', toVal);
                }
                path.setAttribute('class', 'connection-line' + (areaSelector === AREA.execution && edge.adjacent === false ? ' connection-line-cross-layer' : ''));
                svg.appendChild(path);
            });

            const nodesContainer = document.createElement('div');
            nodesContainer.className = 'tree-nodes-container';
            nodesContainer.style.cssText = `position:absolute;top:0;left:0;width:${width}px;height:${height}px;`;
            ctx.tree.appendChild(nodesContainer);

            const taskById = new Map(tasks.map((t) => [t.task_id, t]));
            const parentIds = new Set();
            (edges || []).forEach((e) => {
                const from = e.from;
                if (Array.isArray(from)) from.forEach((id) => parentIds.add(id));
                else parentIds.add(from);
            });
            const leafIds = new Set(Object.keys(nodes).filter((id) => !parentIds.has(id)));

            for (const [taskId, pos] of Object.entries(nodes)) {
                const ids = pos.ids;
                const isMerged = ids && ids.length >= 2;
                let el;
                if (isMerged && areaSelector === AREA.execution) {
                    el = createMergedTaskNodeEl(ids, taskById);
                } else {
                    const task = taskById.get(taskId);
                    if (!task) continue;
                    el = createTaskNodeEl(task);
                    if (areaSelector === AREA.decomposition && leafIds.has(taskId)) {
                        el.classList.add('tree-task-leaf');
                    }
                    if (areaSelector === AREA.execution && task.status && task.status !== 'undone') {
                        el.classList.add('task-status-' + task.status);
                    }
                }
                el.style.position = 'absolute';
                el.style.left = pos.x + 'px';
                el.style.top = pos.y + 'px';
                el.style.width = pos.w + 'px';
                el.style.height = pos.h + 'px';
                nodesContainer.appendChild(el);
            }
        }

        function clear(areaSelector) {
            const ctx = getTreeContainer(areaSelector);
            if (!ctx) return;
            ctx.tree.innerHTML = '';
            ctx.tree.style.width = '';
            ctx.tree.style.height = '';
            ctx.tree.style.minHeight = '';
        }

        return {
            aggregateStatus,
            clear,
            renderFull,
        };
    }

    window.MAARS.createTaskTreeRenderer = createTaskTreeRenderer;
})();
