(function () {
    'use strict';
    window.MAARS = window.MAARS || {};

    function createTaskTreeZoomController(deps) {
        const getTreeContainer = deps?.getTreeContainer;
        const onZoomChange = deps?.onZoomChange || (() => {});
        let treeZoomLevel = 1.0;

        function loadZoomLevel() {
            const saved = sessionStorage.getItem('maars-tree-zoom-level');
            if (saved) {
                treeZoomLevel = parseFloat(saved) || 1.0;
            }
        }

        function saveZoomLevel() {
            sessionStorage.setItem('maars-tree-zoom-level', String(treeZoomLevel));
        }

        function updateZoomDisplay(areaSelector) {
            const ctx = getTreeContainer(areaSelector);
            if (!ctx) return;
            const label = ctx.area.querySelector('.tree-zoom-label');
            if (label) {
                label.textContent = `${Math.round(treeZoomLevel * 100)}%`;
            }
        }

        function changeZoomLevel(delta, areaSelector) {
            treeZoomLevel = Math.max(0.5, Math.min(2.0, treeZoomLevel + delta));
            saveZoomLevel();
            updateZoomDisplay(areaSelector);
            onZoomChange(areaSelector);
        }

        function resetZoomLevel(areaSelector) {
            treeZoomLevel = 1.0;
            saveZoomLevel();
            updateZoomDisplay(areaSelector);
            onZoomChange(areaSelector);
        }

        function initZoomControls(areaSelector) {
            const ctx = getTreeContainer(areaSelector);
            if (!ctx || ctx.area.querySelector('.tree-zoom-controls')) return;

            const controlsDiv = document.createElement('div');
            controlsDiv.className = 'tree-zoom-controls';
            controlsDiv.style.cssText = `
                display: flex;
                align-items: center;
                gap: 8px;
                padding: 8px;
                background: rgba(255,255,255,0.9);
                border-radius: 4px;
                font-size: 12px;
                position: absolute;
                top: 8px;
                right: 8px;
                z-index: 100;
            `;

            const minusBtn = document.createElement('button');
            minusBtn.className = 'tree-zoom-button';
            minusBtn.textContent = '−';
            minusBtn.style.cssText = 'padding: 4px 8px; cursor: pointer; border: 1px solid #ccc; background: #f5f5f5; border-radius: 3px;';
            minusBtn.onclick = () => changeZoomLevel(-0.1, areaSelector);

            const zoomLabel = document.createElement('span');
            zoomLabel.className = 'tree-zoom-label';
            zoomLabel.textContent = '100%';
            zoomLabel.style.cssText = 'width: 35px; text-align: center;';

            const plusBtn = document.createElement('button');
            plusBtn.className = 'tree-zoom-button';
            plusBtn.textContent = '+';
            plusBtn.style.cssText = 'padding: 4px 8px; cursor: pointer; border: 1px solid #ccc; background: #f5f5f5; border-radius: 3px;';
            plusBtn.onclick = () => changeZoomLevel(0.1, areaSelector);

            const resetBtn = document.createElement('button');
            resetBtn.className = 'tree-zoom-reset';
            resetBtn.textContent = 'Reset';
            resetBtn.style.cssText = 'padding: 4px 8px; cursor: pointer; border: 1px solid #ccc; background: #f5f5f5; border-radius: 3px; font-size: 11px;';
            resetBtn.onclick = () => resetZoomLevel(areaSelector);

            controlsDiv.appendChild(minusBtn);
            controlsDiv.appendChild(zoomLabel);
            controlsDiv.appendChild(plusBtn);
            controlsDiv.appendChild(resetBtn);

            ctx.area.style.position = 'relative';
            ctx.area.appendChild(controlsDiv);
        }

        function getLevel() {
            return treeZoomLevel;
        }

        function setLevel(level) {
            treeZoomLevel = Math.max(0.5, Math.min(2.0, level));
            saveZoomLevel();
        }

        return {
            changeZoomLevel,
            getLevel,
            initZoomControls,
            loadZoomLevel,
            resetZoomLevel,
            setLevel,
            updateZoomDisplay,
        };
    }

    window.MAARS.createTaskTreeZoomController = createTaskTreeZoomController;
})();
