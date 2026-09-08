    // ---- Benchmark rendering ----
    // Extracted from viewer.js for size management.
    // Depends on: EMBEDDED_DATA (global), escapeHtml() (defined in viewer.js, loaded after this file)
    function renderBenchmark() {
      const data = EMBEDDED_DATA.benchmark;
      if (!data) return;

      // Show the tabs
      document.getElementById("view-tabs").style.display = "flex";

      const container = document.getElementById("benchmark-content");
      const summary = data.run_summary || {};
      const metadata = data.metadata || {};
      const notes = data.notes || [];

      let html = "";

      // Header
      html += "<h2 style='font-family: Poppins, sans-serif; margin-bottom: 0.5rem;'>Benchmark Results</h2>";
      html += "<p style='color: var(--text-muted); font-size: 0.875rem; margin-bottom: 1.25rem;'>";
      if (metadata.skill_name) html += "<strong>" + escapeHtml(metadata.skill_name) + "</strong> &mdash; ";
      if (metadata.timestamp) html += metadata.timestamp + " &mdash; ";
      if (metadata.evals_run) html += "Evals: " + metadata.evals_run.join(", ") + " &mdash; ";
      html += (metadata.runs_per_configuration || "?") + " runs per configuration";
      html += "</p>";

      // Summary table
      html += '<table class="benchmark-table">';

      function fmtStat(stat, pct) {
        if (!stat) return "—";
        const suffix = pct ? "%" : "";
        const m = pct ? (stat.mean * 100).toFixed(0) : stat.mean.toFixed(1);
        const s = pct ? (stat.stddev * 100).toFixed(0) : stat.stddev.toFixed(1);
        return m + suffix + " ± " + s + suffix;
      }

      function deltaClass(val) {
        if (!val) return "";
        const n = parseFloat(val);
        if (n > 0) return "benchmark-delta-positive";
        if (n < 0) return "benchmark-delta-negative";
        return "";
      }

      // Discover config names dynamically (everything except "delta")
      const configs = Object.keys(summary).filter(k => k !== "delta");
      const configA = configs[0] || "config_a";
      const configB = configs[1] || "config_b";
      const labelA = configA.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
      const labelB = configB.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
      const a = summary[configA] || {};
      const b = summary[configB] || {};
      const delta = summary.delta || {};

      html += "<thead><tr><th>Metric</th><th>" + escapeHtml(labelA) + "</th><th>" + escapeHtml(labelB) + "</th><th>Delta</th></tr></thead>";
      html += "<tbody>";

      html += "<tr><td><strong>Pass Rate</strong></td>";
      html += "<td>" + fmtStat(a.pass_rate, true) + "</td>";
      html += "<td>" + fmtStat(b.pass_rate, true) + "</td>";
      html += '<td class="' + deltaClass(delta.pass_rate) + '">' + (delta.pass_rate || "—") + "</td></tr>";

      // Time (only show row if data exists)
      if (a.time_seconds || b.time_seconds) {
        html += "<tr><td><strong>Time (s)</strong></td>";
        html += "<td>" + fmtStat(a.time_seconds, false) + "</td>";
        html += "<td>" + fmtStat(b.time_seconds, false) + "</td>";
        html += '<td class="' + deltaClass(delta.time_seconds) + '">' + (delta.time_seconds ? delta.time_seconds + "s" : "—") + "</td></tr>";
      }

      // Tokens (only show row if data exists)
      if (a.tokens || b.tokens) {
        html += "<tr><td><strong>Tokens</strong></td>";
        html += "<td>" + fmtStat(a.tokens, false) + "</td>";
        html += "<td>" + fmtStat(b.tokens, false) + "</td>";
        html += '<td class="' + deltaClass(delta.tokens) + '">' + (delta.tokens || "—") + "</td></tr>";
      }

      html += "</tbody></table>";

      // Per-eval breakdown (if runs data available)
      const runs = data.runs || [];
      if (runs.length > 0) {
        const evalIds = [...new Set(runs.map(r => r.eval_id))].sort((a, b) => a - b);

        html += "<h3 style='font-family: Poppins, sans-serif; margin-bottom: 0.75rem;'>Per-Eval Breakdown</h3>";

        const hasTime = runs.some(r => r.result && r.result.time_seconds != null);
        const hasErrors = runs.some(r => r.result && r.result.errors > 0);

        for (const evalId of evalIds) {
          const evalRuns = runs.filter(r => r.eval_id === evalId);
          const evalName = evalRuns[0] && evalRuns[0].eval_name ? evalRuns[0].eval_name : "Eval " + evalId;

          html += "<h4 style='font-family: Poppins, sans-serif; margin: 1rem 0 0.5rem; color: var(--text);'>" + escapeHtml(evalName) + "</h4>";
          html += '<table class="benchmark-table">';
          html += "<thead><tr><th>Config</th><th>Run</th><th>Pass Rate</th>";
          if (hasTime) html += "<th>Time (s)</th>";
          if (hasErrors) html += "<th>Crashes During Execution</th>";
          html += "</tr></thead>";
          html += "<tbody>";

          // Group by config and render with average rows
          const configGroups = [...new Set(evalRuns.map(r => r.configuration))];
          for (let ci = 0; ci < configGroups.length; ci++) {
            const config = configGroups[ci];
            const configRuns = evalRuns.filter(r => r.configuration === config);
            if (configRuns.length === 0) continue;

            const rowClass = ci === 0 ? "benchmark-row-with" : "benchmark-row-without";
            const configLabel = config.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());

            for (const run of configRuns) {
              const r = run.result || {};
              const prClass = r.pass_rate >= 0.8 ? "benchmark-delta-positive" : r.pass_rate < 0.5 ? "benchmark-delta-negative" : "";
              html += '<tr class="' + rowClass + '">';
              html += "<td>" + configLabel + "</td>";
              html += "<td>" + run.run_number + "</td>";
              html += '<td class="' + prClass + '">' + ((r.pass_rate || 0) * 100).toFixed(0) + "% (" + (r.passed || 0) + "/" + (r.total || 0) + ")</td>";
              if (hasTime) html += "<td>" + (r.time_seconds != null ? r.time_seconds.toFixed(1) : "—") + "</td>";
              if (hasErrors) html += "<td>" + (r.errors || 0) + "</td>";
              html += "</tr>";
            }

            // Average row
            const rates = configRuns.map(r => (r.result || {}).pass_rate || 0);
            const avgRate = rates.reduce((a, b) => a + b, 0) / rates.length;
            const avgPrClass = avgRate >= 0.8 ? "benchmark-delta-positive" : avgRate < 0.5 ? "benchmark-delta-negative" : "";
            html += '<tr class="benchmark-row-avg ' + rowClass + '">';
            html += "<td>" + configLabel + "</td>";
            html += "<td>Avg</td>";
            html += '<td class="' + avgPrClass + '">' + (avgRate * 100).toFixed(0) + "%</td>";
            if (hasTime) {
              const times = configRuns.map(r => (r.result || {}).time_seconds).filter(t => t != null);
              html += "<td>" + (times.length ? (times.reduce((a, b) => a + b, 0) / times.length).toFixed(1) : "—") + "</td>";
            }
            if (hasErrors) html += "<td></td>";
            html += "</tr>";
          }
          html += "</tbody></table>";

          // Per-assertion detail for this eval
          const runsWithExpectations = {};
          for (const config of configGroups) {
            runsWithExpectations[config] = evalRuns.filter(r => r.configuration === config && r.expectations && r.expectations.length > 0);
          }
          const hasAnyExpectations = Object.values(runsWithExpectations).some(runs => runs.length > 0);
          if (hasAnyExpectations) {
            // Collect all unique assertion texts across all configs
            const allAssertions = [];
            const seen = new Set();
            for (const config of configGroups) {
              for (const run of runsWithExpectations[config]) {
                for (const exp of (run.expectations || [])) {
                  if (!seen.has(exp.text)) {
                    seen.add(exp.text);
                    allAssertions.push(exp.text);
                  }
                }
              }
            }

            html += '<table class="benchmark-table" style="margin-top: 0.5rem;">';
            html += "<thead><tr><th>Assertion</th>";
            for (const config of configGroups) {
              const label = config.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
              html += "<th>" + escapeHtml(label) + "</th>";
            }
            html += "</tr></thead><tbody>";

            for (const assertionText of allAssertions) {
              html += "<tr><td>" + escapeHtml(assertionText) + "</td>";

              for (const config of configGroups) {
                html += "<td>";
                for (const run of runsWithExpectations[config]) {
                  const exp = (run.expectations || []).find(e => e.text === assertionText);
                  if (exp) {
                    const cls = exp.passed ? "benchmark-delta-positive" : "benchmark-delta-negative";
                    const icon = exp.passed ? "\u2713" : "\u2717";
                    html += '<span class="' + cls + '" title="Run ' + run.run_number + ': ' + escapeHtml(exp.evidence || "") + '">' + icon + "</span> ";
                  } else {
                    html += "— ";
                  }
                }
                html += "</td>";
              }
              html += "</tr>";
            }
            html += "</tbody></table>";
          }
        }
      }

      // Notes
      if (notes.length > 0) {
        html += '<div class="benchmark-notes">';
        html += "<h3>Analysis Notes</h3>";
        html += "<ul>";
        for (const note of notes) {
          html += "<li>" + escapeHtml(note) + "</li>";
        }
        html += "</ul></div>";
      }

      container.innerHTML = html;
    }
