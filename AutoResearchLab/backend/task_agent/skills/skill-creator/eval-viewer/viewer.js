    // ---- Embedded data (injected by generate_review.py) ----
    /*__EMBEDDED_DATA__*/

    // ---- State ----
    let feedbackMap = {};  // run_id -> feedback text
    let currentIndex = 0;
    let visitedRuns = new Set();

    // ---- Init ----
    async function init() {
      // Load saved feedback from server — but only if this isn't a fresh
      // iteration (indicated by previous_feedback being present). When
      // previous feedback exists, the feedback.json on disk is stale from
      // the prior iteration and should not pre-fill the textareas.
      const hasPrevious = Object.keys(EMBEDDED_DATA.previous_feedback || {}).length > 0
        || Object.keys(EMBEDDED_DATA.previous_outputs || {}).length > 0;
      if (!hasPrevious) {
        try {
          const resp = await fetch("/api/feedback");
          const data = await resp.json();
          if (data.reviews) {
            for (const r of data.reviews) feedbackMap[r.run_id] = r.feedback;
          }
        } catch { /* first run, no feedback yet */ }
      }

      document.getElementById("skill-name").textContent = EMBEDDED_DATA.skill_name;
      showRun(0);

      // Wire up feedback auto-save
      const textarea = document.getElementById("feedback");
      let saveTimeout = null;
      textarea.addEventListener("input", () => {
        clearTimeout(saveTimeout);
        document.getElementById("feedback-status").textContent = "";
        saveTimeout = setTimeout(() => saveCurrentFeedback(), 800);
      });
    }

    // ---- Navigation ----
    function navigate(delta) {
      const newIndex = currentIndex + delta;
      if (newIndex >= 0 && newIndex < EMBEDDED_DATA.runs.length) {
        saveCurrentFeedback();
        showRun(newIndex);
      }
    }

    function updateNavButtons() {
      document.getElementById("prev-btn").disabled = currentIndex === 0;
      document.getElementById("next-btn").disabled =
        currentIndex === EMBEDDED_DATA.runs.length - 1;
    }

    // ---- Show a run ----
    function showRun(index) {
      currentIndex = index;
      const run = EMBEDDED_DATA.runs[index];

      // Progress
      document.getElementById("progress").textContent =
        `${index + 1} of ${EMBEDDED_DATA.runs.length}`;

      // Prompt
      document.getElementById("prompt-text").textContent = run.prompt;

      // Config badge
      const badge = document.getElementById("config-badge");
      const configMatch = run.id.match(/(with_skill|without_skill|new_skill|old_skill)/);
      if (configMatch) {
        const config = configMatch[1];
        const isBaseline = config === "without_skill" || config === "old_skill";
        badge.textContent = config.replace(/_/g, " ");
        badge.className = "config-badge " + (isBaseline ? "config-baseline" : "config-primary");
        badge.style.display = "inline-block";
      } else {
        badge.style.display = "none";
      }

      // Outputs
      renderOutputs(run);

      // Previous outputs
      renderPrevOutputs(run);

      // Grades
      renderGrades(run);

      // Previous feedback
      const prevFb = (EMBEDDED_DATA.previous_feedback || {})[run.id];
      const prevEl = document.getElementById("prev-feedback");
      if (prevFb) {
        document.getElementById("prev-feedback-text").textContent = prevFb;
        prevEl.style.display = "block";
      } else {
        prevEl.style.display = "none";
      }

      // Feedback
      document.getElementById("feedback").value = feedbackMap[run.id] || "";
      document.getElementById("feedback-status").textContent = "";

      updateNavButtons();

      // Track visited runs and promote done button when all visited
      visitedRuns.add(index);
      const doneBtn = document.getElementById("done-btn");
      if (visitedRuns.size >= EMBEDDED_DATA.runs.length) {
        doneBtn.classList.add("ready");
      }

      // Scroll main content to top
      document.querySelector(".main").scrollTop = 0;
    }

    // ---- Render outputs ----
    function renderOutputs(run) {
      const container = document.getElementById("outputs-body");
      container.innerHTML = "";

      const outputs = run.outputs || [];
      if (outputs.length === 0) {
        container.innerHTML = '<div class="empty-state">No output files</div>';
        return;
      }

      for (const file of outputs) {
        const fileDiv = document.createElement("div");
        fileDiv.className = "output-file";

        // Always show file header with download link
        const header = document.createElement("div");
        header.className = "output-file-header";
        const nameSpan = document.createElement("span");
        nameSpan.textContent = file.name;
        header.appendChild(nameSpan);
        const dlBtn = document.createElement("a");
        dlBtn.className = "dl-btn";
        dlBtn.textContent = "Download";
        dlBtn.download = file.name;
        dlBtn.href = getDownloadUri(file);
        header.appendChild(dlBtn);
        fileDiv.appendChild(header);

        const content = document.createElement("div");
        content.className = "output-file-content";

        if (file.type === "text") {
          const pre = document.createElement("pre");
          pre.textContent = file.content;
          content.appendChild(pre);
        } else if (file.type === "image") {
          const img = document.createElement("img");
          img.src = file.data_uri;
          img.alt = file.name;
          content.appendChild(img);
        } else if (file.type === "pdf") {
          const iframe = document.createElement("iframe");
          iframe.src = file.data_uri;
          content.appendChild(iframe);
        } else if (file.type === "xlsx") {
          renderXlsx(content, file.data_b64);
        } else if (file.type === "binary") {
          const a = document.createElement("a");
          a.className = "download-link";
          a.href = file.data_uri;
          a.download = file.name;
          a.textContent = "Download " + file.name;
          content.appendChild(a);
        } else if (file.type === "error") {
          const pre = document.createElement("pre");
          pre.textContent = file.content;
          pre.style.color = "var(--red)";
          content.appendChild(pre);
        }

        fileDiv.appendChild(content);
        container.appendChild(fileDiv);
      }
    }

    // ---- XLSX rendering via SheetJS ----
    function renderXlsx(container, b64Data) {
      try {
        const raw = Uint8Array.from(atob(b64Data), c => c.charCodeAt(0));
        const wb = XLSX.read(raw, { type: "array" });

        for (let i = 0; i < wb.SheetNames.length; i++) {
          const sheetName = wb.SheetNames[i];
          const ws = wb.Sheets[sheetName];

          if (wb.SheetNames.length > 1) {
            const sheetLabel = document.createElement("div");
            sheetLabel.style.cssText =
              "font-weight:600; font-size:0.8rem; color:#b0aea5; margin-top:0.5rem; margin-bottom:0.25rem;";
            sheetLabel.textContent = "Sheet: " + sheetName;
            container.appendChild(sheetLabel);
          }

          const htmlStr = XLSX.utils.sheet_to_html(ws, { editable: false });
          const wrapper = document.createElement("div");
          wrapper.innerHTML = htmlStr;
          container.appendChild(wrapper);
        }
      } catch (err) {
        container.textContent = "Error rendering spreadsheet: " + err.message;
      }
    }

    // ---- Grades ----
    function renderGrades(run) {
      const section = document.getElementById("grades-section");
      const content = document.getElementById("grades-content");

      if (!run.grading) {
        section.style.display = "none";
        return;
      }

      const grading = run.grading;
      section.style.display = "block";
      // Reset to collapsed
      content.classList.remove("open");
      document.getElementById("grades-arrow").classList.remove("open");

      const summary = grading.summary || {};
      const expectations = grading.expectations || [];

      let html = '<div style="padding: 1rem;">';

      // Summary line
        e.preventDefault();
        navigate(1);
      }
    });

    // ---- Util ----
    function getDownloadUri(file) {
      if (file.data_uri) return file.data_uri;
      if (file.data_b64) return "data:application/octet-stream;base64," + file.data_b64;
      if (file.type === "text") return "data:text/plain;charset=utf-8," + encodeURIComponent(file.content);
      return "#";
    }

    function escapeHtml(text) {
      const div = document.createElement("div");
      div.textContent = text;
      return div.innerHTML;
    }

    // ---- View switching ----
    function switchView(view) {
      document.querySelectorAll(".view-tab").forEach(t => t.classList.remove("active"));
      document.querySelectorAll(".view-panel").forEach(p => p.classList.remove("active"));
      document.querySelector(`[onclick="switchView('${view}')"]`).classList.add("active");
      document.getElementById("panel-" + view).classList.add("active");
    }

    // ---- Benchmark rendering ----
    // ---- Start ----
    init();
    renderBenchmark();