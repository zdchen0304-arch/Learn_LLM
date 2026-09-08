(function () {
    'use strict';

    function getQueryParam(name) {
        try {
            const params = new URLSearchParams(window.location.search || '');
            return (params.get(name) || '').trim();
        } catch (_) {
            return '';
        }
    }

    function getResearchIdFromUrl() {
        const byQuery = getQueryParam('researchId') || getQueryParam('rid');
        if (byQuery) return byQuery;
        const hash = (window.location.hash || '').replace(/^#/, '');
        const match = hash.match(/^\/r\/(.+)$/);
        if (match) return decodeURIComponent(match[1]);
        return '';
    }

    function navigateToCreateResearch() {
        window.location.href = 'research.html';
    }

    function navigateToResearch(researchId) {
        if (!researchId) return;
        window.location.href = 'research_detail.html?researchId=' + encodeURIComponent(researchId);
    }

    function scrollToDetails() {
        const host = document.getElementById('researchDetailHost');
        if (!host) return;
        host.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    window.MAARS = window.MAARS || {};
    window.MAARS.researchNavUtils = {
        getQueryParam,
        getResearchIdFromUrl,
        navigateToCreateResearch,
        navigateToResearch,
        scrollToDetails,
    };
})();
