const DATA_FILES = {
  summary: "public/data/summary.json",
  monthly: "public/data/monthly_sales.json",
  mix: "public/data/product_mix.json",
  foam: "public/data/foam_analytics.json",
  fabric: "public/data/fabric_analytics.json",
  quality: "public/data/data_quality.json",
};

const PRODUCT_CATEGORIES = new Set(["foam", "fabric", "dacron", "covers_upholstery", "other_product", "unknown"]);
const COLORS = ["#087f5b", "#0ca678", "#168aad", "#f2c94c", "#d94848", "#74b816", "#15aabf"];
const CALENDAR_MONTHS = [
  ["01", "Jan"],
  ["02", "Feb"],
  ["03", "Mar"],
  ["04", "Apr"],
  ["05", "May"],
  ["06", "Jun"],
  ["07", "Jul"],
  ["08", "Aug"],
  ["09", "Sep"],
  ["10", "Oct"],
  ["11", "Nov"],
  ["12", "Dec"],
];

const state = {
  data: null,
  startMonth: null,
  endMonth: null,
  activeTab: "overview",
  selectedFoamCode: null,
};

const currency = new Intl.NumberFormat("en-AU", {
  style: "currency",
  currency: "AUD",
  maximumFractionDigits: 0,
});

const number = new Intl.NumberFormat("en-AU");

function fmtMoney(value) {
  return currency.format(value || 0);
}

function fmtNumber(value) {
  return number.format(Math.round(value || 0));
}

function fmtPercent(value) {
  return `${Math.round((value || 0) * 100)}%`;
}

function byMonthRange(row) {
  const key = row.month || row.key;
  if (!key || key.length < 7) return true;
  if (state.startMonth && key < state.startMonth) return false;
  if (state.endMonth && key > state.endMonth) return false;
  return true;
}

function filteredMonthly() {
  return state.data.monthly.monthly.filter(byMonthRange);
}

function filteredRows(rows) {
  return rows.filter(byMonthRange);
}

function sum(rows, key) {
  return rows.reduce((total, row) => total + (Number(row[key]) || 0), 0);
}

function groupSum(rows, keyField, valueField = "revenue") {
  const grouped = new Map();
  rows.forEach((row) => {
    const key = row[keyField] || "unknown";
    grouped.set(key, (grouped.get(key) || 0) + (Number(row[valueField]) || 0));
  });
  return [...grouped.entries()]
    .map(([key, value]) => ({ key, value }))
    .sort((a, b) => b.value - a.value);
}

function section(title, subtitle, content) {
  return `
    <div class="section">
      <div class="section-head">
        <div>
          <h2>${title}</h2>
          ${subtitle ? `<p>${subtitle}</p>` : ""}
        </div>
      </div>
      ${content}
    </div>
  `;
}

function metric(label, value, note = "") {
  return `
    <div class="metric">
      <div class="label">${label}</div>
      <div class="value">${value}</div>
      ${note ? `<div class="note">${note}</div>` : ""}
    </div>
  `;
}

function metricGrid(items) {
  return `<div class="metric-grid">${items.join("")}</div>`;
}

function table(rows, columns) {
  if (!rows.length) return `<div class="empty">No rows in this date range</div>`;
  return `
    <div class="table-wrap">
      <table>
        <thead>
          <tr>${columns.map((col) => `<th>${col.label}</th>`).join("")}</tr>
        </thead>
        <tbody>
          ${rows
            .map(
              (row) => `
                <tr>
                  ${columns.map((col) => `<td>${col.format ? col.format(row[col.key], row) : row[col.key]}</td>`).join("")}
                </tr>
              `,
            )
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

function lineChart(rows, key = "revenue", label = "Revenue", formatter = fmtMoney) {
  const data = rows.filter((row) => Number.isFinite(Number(row[key])));
  if (data.length < 2) return `<div class="empty">Not enough data</div>`;
  const width = 900;
  const height = 320;
  const pad = { top: 18, right: 20, bottom: 42, left: 76 };
  const max = Math.max(...data.map((row) => Number(row[key]) || 0));
  const min = Math.min(0, ...data.map((row) => Number(row[key]) || 0));
  const x = (index) => pad.left + (index * (width - pad.left - pad.right)) / (data.length - 1);
  const y = (value) => height - pad.bottom - ((value - min) / (max - min || 1)) * (height - pad.top - pad.bottom);
  const points = data.map((row, index) => `${x(index)},${y(Number(row[key]) || 0)}`).join(" ");
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((ratio) => min + (max - min) * ratio);
  const labelEvery = Math.max(1, Math.ceil(data.length / 10));
  return `
    <div class="viz">
      <h3>${label}</h3>
      <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${label}">
        ${ticks
          .map((tick) => {
            const ty = y(tick);
            return `<line x1="${pad.left}" x2="${width - pad.right}" y1="${ty}" y2="${ty}" stroke="#d8e3df" />
                    <text class="axis-text" x="8" y="${ty + 4}">${formatter(tick)}</text>`;
          })
          .join("")}
        <polyline fill="none" stroke="#087f5b" stroke-width="4" points="${points}" />
        ${data
          .filter((_, index) => index % labelEvery === 0 || index === data.length - 1)
          .map((row, index) => {
            const originalIndex = data.indexOf(row);
            return `<text class="axis-text" x="${x(originalIndex) - 22}" y="${height - 12}">${row.key}</text>`;
          })
          .join("")}
      </svg>
    </div>
  `;
}

function barChart(rows, labelKey = "key", valueKey = "revenue", title = "", formatter = null) {
  const data = rows.slice(0, 12).filter((row) => Number(row[valueKey]) > 0);
  if (!data.length) return `<div class="empty">No data</div>`;
  const max = Math.max(...data.map((row) => Number(row[valueKey])));
  const valueFormatter = formatter || (valueKey === "revenue" ? fmtMoney : fmtNumber);
  return `
    <div class="viz">
      ${title ? `<h3>${title}</h3>` : ""}
      ${data
        .map((row, index) => {
          const pct = Math.max(2, (Number(row[valueKey]) / max) * 100);
          return `
            <div class="bar-row">
              <div class="bar-label">${row[labelKey]}</div>
              <div class="bar-track"><div class="bar-fill" style="width:${pct}%;background:${COLORS[index % COLORS.length]}"></div></div>
              <div class="bar-value">${valueFormatter(row[valueKey])}</div>
            </div>
          `;
        })
        .join("")}
    </div>
  `;
}

function addBarCss() {
  if (document.getElementById("barCss")) return;
  const style = document.createElement("style");
  style.id = "barCss";
  style.textContent = `
    .bar-row{display:grid;grid-template-columns:minmax(88px,170px) minmax(120px,1fr) minmax(80px,120px);gap:10px;align-items:center;margin:9px 0}
    .bar-label{font-weight:800;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
    .bar-track{height:16px;border-radius:8px;background:#edf4f1;overflow:hidden}
    .bar-fill{height:100%;border-radius:8px}
    .bar-value{text-align:right;color:var(--muted);font-weight:800}
    @media(max-width:620px){.bar-row{grid-template-columns:1fr}.bar-value{text-align:left}.bar-track{width:100%}}
  `;
  document.head.appendChild(style);
}

function filteredCategoryTotals() {
  return groupSum(filteredRows(state.data.monthly.category_monthly), "category").map((row) => ({
    key: row.key,
    revenue: row.value,
  }));
}

function foamMonthlyAverages(foamCode) {
  const monthDenominators = new Map(CALENDAR_MONTHS.map(([month]) => [month, 0]));
  filteredMonthly().forEach((row) => {
    const month = String(row.key || "").slice(5, 7);
    if (monthDenominators.has(month)) monthDenominators.set(month, monthDenominators.get(month) + 1);
  });

  const monthlyTotals = new Map(
    CALENDAR_MONTHS.map(([month, label]) => [
      month,
      {
        key: label,
        month,
        revenue: 0,
        line_count: 0,
        invoice_count: 0,
        months_observed: monthDenominators.get(month) || 0,
      },
    ]),
  );

  filteredRows(state.data.foam.code_monthly)
    .filter((row) => row.foam_code === foamCode)
    .forEach((row) => {
      const month = String(row.month || "").slice(5, 7);
      const target = monthlyTotals.get(month);
      if (!target) return;
      target.revenue += Number(row.revenue) || 0;
      target.line_count += Number(row.line_count) || 0;
      target.invoice_count += Number(row.invoice_count) || 0;
    });

  return [...monthlyTotals.values()].map((row) => ({
    ...row,
    avg_revenue: row.months_observed ? row.revenue / row.months_observed : 0,
    avg_lines: row.months_observed ? row.line_count / row.months_observed : 0,
  }));
}

function renderOverview() {
  const months = filteredMonthly();
  const revenue = sum(months, "revenue");
  const invoices = sum(months, "invoice_count");
  const productRevenue = filteredCategoryTotals()
    .filter((row) => PRODUCT_CATEGORIES.has(row.key))
    .reduce((total, row) => total + row.revenue, 0);
  const panel = document.getElementById("overview");
  panel.innerHTML =
    section(
      "Overview",
      `${state.data.summary.date_min} to ${state.data.summary.date_max}. Filters use monthly aggregates.`,
      metricGrid([
        metric("Gross revenue", fmtMoney(revenue), "Selected months"),
        metric("Product and service revenue", fmtMoney(productRevenue), "Discounts, delivery, banking separated"),
        metric("Invoices", fmtNumber(invoices), "Monthly unique invoices summed"),
        metric("Average order value", fmtMoney(invoices ? revenue / invoices : 0), "Gross revenue divided by invoice count"),
      ]),
    ) +
    `<div class="grid-2">
      ${lineChart(months, "revenue", "Monthly revenue", fmtMoney)}
      ${barChart(filteredCategoryTotals(), "key", "revenue", "Category revenue")}
    </div>`;
}

function renderSales() {
  const months = filteredMonthly();
  const yearly = state.data.monthly.yearly.filter((row) => {
    if (!state.startMonth && !state.endMonth) return true;
    return months.some((month) => month.key.startsWith(row.key));
  });
  document.getElementById("sales").innerHTML =
    section(
      "Sales Trends",
      "Revenue, invoice volume, and average value by month and year.",
      `<div class="grid-2">${lineChart(months, "revenue", "Monthly revenue", fmtMoney)}${lineChart(months, "invoice_count", "Monthly invoice count", fmtNumber)}</div>`,
    ) +
    section(
      "Yearly Totals",
      "",
      table(yearly, [
        { key: "key", label: "Year" },
        { key: "revenue", label: "Revenue", format: fmtMoney },
        { key: "invoice_count", label: "Invoices", format: fmtNumber },
        { key: "line_count", label: "Lines", format: fmtNumber },
      ]),
    );
}

function renderFoam() {
  const foam = state.data.foam;
  const monthly = filteredRows(foam.monthly);
  const envMonthly = groupSum(filteredRows(foam.environment_monthly), "environment");
  const foamOptions = [
    ...foam.top_codes.filter((row) => row.key !== "unknown").map((row) => row.key),
    ...foam.top_codes.filter((row) => row.key === "unknown").map((row) => row.key),
  ];
  if (!state.selectedFoamCode || !foamOptions.includes(state.selectedFoamCode)) {
    state.selectedFoamCode = foamOptions[0] || "unknown";
  }
  const selectedAverages = foamMonthlyAverages(state.selectedFoamCode);
  document.getElementById("foam").innerHTML =
    section(
      "Foam Analytics",
      "Foam revenue, type, thickness, and indoor/outdoor split. Dimension length and width should be treated cautiously until a cleanup pass.",
      metricGrid([
        metric("Foam revenue", fmtMoney(sum(monthly, "revenue")), "Selected months"),
        metric("Foam lines", fmtNumber(sum(monthly, "line_count")), "Selected months"),
        metric("Top foam code", foam.top_codes[0]?.key || "n/a", foam.top_codes[0] ? fmtMoney(foam.top_codes[0].revenue) : ""),
        metric("Top thickness", `${foam.top_thicknesses[0]?.key || "n/a"} mm`, foam.top_thicknesses[0] ? fmtMoney(foam.top_thicknesses[0].revenue) : ""),
      ]),
    ) +
    `<div class="grid-2">${lineChart(monthly, "revenue", "Foam revenue over time", fmtMoney)}${barChart(envMonthly, "key", "value", "Indoor vs outdoor foam")}</div>` +
    section(
      "Average Sales By Month Of Year",
      "Select a foam type to compare its average monthly revenue across calendar months. Averages include months with zero sales inside the selected date range.",
      `
        <div class="selector-row">
          <label for="foamCodeSelect">Foam type</label>
          <select id="foamCodeSelect">
            ${foamOptions.map((code) => `<option value="${code}" ${code === state.selectedFoamCode ? "selected" : ""}>${code}</option>`).join("")}
          </select>
        </div>
        <div class="grid-2">
          ${barChart(selectedAverages, "key", "avg_revenue", `${state.selectedFoamCode} average revenue by calendar month`, fmtMoney)}
          ${table(selectedAverages, [
            { key: "key", label: "Month" },
            { key: "avg_revenue", label: "Avg revenue", format: fmtMoney },
            { key: "revenue", label: "Total revenue", format: fmtMoney },
            { key: "avg_lines", label: "Avg lines", format: (value) => value.toFixed(1) },
            { key: "months_observed", label: "Months", format: fmtNumber },
          ])}
        </div>
      `,
    ) +
    `<div class="grid-2">
      ${barChart(foam.top_codes, "key", "revenue", "Foam type ranking")}
      ${barChart(foam.top_thicknesses, "key", "revenue", "Foam thickness ranking")}
    </div>` +
    section(
      "Top Foam Types",
      "",
      table(foam.top_codes.slice(0, 20), [
        { key: "key", label: "Foam code" },
        { key: "revenue", label: "Revenue", format: fmtMoney },
        { key: "line_count", label: "Lines", format: fmtNumber },
        { key: "invoice_count", label: "Invoices", format: fmtNumber },
        { key: "avg_confidence", label: "Avg confidence", format: (value) => fmtPercent(value) },
      ]),
    );
  const selector = document.getElementById("foamCodeSelect");
  if (selector) {
    selector.addEventListener("change", () => {
      state.selectedFoamCode = selector.value;
      renderFoam();
    });
  }
}

function renderFabric() {
  const fabric = state.data.fabric;
  const monthly = filteredRows(fabric.monthly);
  const envMonthly = groupSum(filteredRows(fabric.environment_monthly), "environment");
  document.getElementById("fabric").innerHTML =
    section(
      "Fabric Analytics",
      "Fabric environment is inferred. Outdoor-suitable does not prove the customer used it outdoors.",
      metricGrid([
        metric("Fabric revenue", fmtMoney(sum(monthly, "revenue")), "Selected months"),
        metric("Fabric lines", fmtNumber(sum(monthly, "line_count")), "Selected months"),
        metric("Top brand", fabric.top_brands[0]?.key || "n/a", fabric.top_brands[0] ? fmtMoney(fabric.top_brands[0].revenue) : ""),
        metric("Outdoor-suitable share", fmtPercent((envMonthly.find((row) => row.key === "outdoor_suitable")?.value || 0) / (sum(envMonthly, "value") || 1)), "Revenue share"),
      ]),
    ) +
    `<div class="grid-2">${lineChart(monthly, "revenue", "Fabric revenue over time", fmtMoney)}${barChart(envMonthly, "key", "value", "Fabric environment inference")}</div>` +
    `<div class="grid-2">
      ${barChart(fabric.top_brands, "key", "revenue", "Fabric brand ranking")}
      ${barChart(fabric.top_names, "key", "revenue", "Fabric name ranking")}
    </div>` +
    section(
      "Top Fabric Brands",
      "",
      table(fabric.top_brands.slice(0, 20), [
        { key: "key", label: "Brand" },
        { key: "revenue", label: "Revenue", format: fmtMoney },
        { key: "line_count", label: "Lines", format: fmtNumber },
        { key: "invoice_count", label: "Invoices", format: fmtNumber },
        { key: "avg_confidence", label: "Avg confidence", format: (value) => fmtPercent(value) },
      ]),
    );
}

function renderMix() {
  const totals = filteredCategoryTotals();
  document.getElementById("mix").innerHTML =
    section(
      "Product Mix",
      "Revenue by extracted category, with non-product rows separated for reconciliation.",
      `<div class="grid-2">${barChart(totals, "key", "revenue", "Selected category revenue")}${barChart(state.data.mix.category, "key", "line_count", "All-time category line count")}</div>`,
    ) +
    section(
      "Category Table",
      "",
      table(totals, [
        { key: "key", label: "Category" },
        { key: "revenue", label: "Revenue", format: fmtMoney },
      ]),
    );
}

function renderQuality() {
  const q = state.data.quality;
  const validation = q.validation || {};
  document.getElementById("quality").innerHTML =
    section(
      "Data Quality",
      "The Gemini output is structurally complete. Some low-confidence foam rows and dimensions need caution.",
      metricGrid([
        metric("Integrity passed", validation.passed_integrity ? "Yes" : "No", "Every source row mapped once"),
        metric("Review rows", fmtNumber(state.data.summary.review_needed_count), `${fmtPercent(state.data.summary.review_needed_rate)} of rows`),
        metric("Average confidence", fmtPercent(state.data.summary.average_confidence), "All Gemini rows"),
        metric("Low-confidence not flagged", fmtNumber(Object.values(q.low_confidence_not_reviewed || {}).reduce((a, b) => a + Number(b || 0), 0)), "Handled as caution in dashboard"),
      ]),
    ) +
    `<div class="grid-2">
      ${barChart(Object.entries(q.confidence_distribution || {}).map(([key, count]) => ({ key, count })), "key", "count", "Confidence distribution")}
      <div class="note-box warning">
        <h3>Known Caveats</h3>
        <p>Foam type, thickness, fabric ranking, and category trends are usable for a first dashboard. Detailed length/width dimensions need a cleanup pass because some rows treat piece counts as dimensions.</p>
        <div class="pill-row">
          ${(validation.notes || []).map((note) => `<span class="pill">${note}</span>`).join("")}
        </div>
      </div>
    </div>` +
    section(
      "Dimension Examples To Review",
      "",
      table(q.dimension_quality_examples || [], [
        { key: "source_row_id", label: "Row", format: fmtNumber },
        { key: "category", label: "Category" },
        { key: "dimensions_mm", label: "Dimensions", format: (value) => JSON.stringify(value) },
        { key: "evidence", label: "Evidence", format: (value) => (value || []).join(", ") },
      ]),
    );
}

function renderAll() {
  addBarCss();
  renderOverview();
  renderSales();
  renderFoam();
  renderFabric();
  renderMix();
  renderQuality();
}

function setActiveTab(tabName) {
  state.activeTab = tabName;
  document.querySelectorAll(".tab").forEach((button) => {
    button.classList.toggle("active", button.dataset.tab === tabName);
  });
  document.querySelectorAll(".panel").forEach((panel) => {
    panel.classList.toggle("active", panel.id === tabName);
  });
}

async function loadData() {
  const entries = await Promise.all(
    Object.entries(DATA_FILES).map(async ([key, path]) => {
      const response = await fetch(path);
      if (!response.ok) throw new Error(`Failed to load ${path}`);
      return [key, await response.json()];
    }),
  );
  return Object.fromEntries(entries);
}

function initFilters() {
  const months = state.data.monthly.monthly.map((row) => row.key).sort();
  const startInput = document.getElementById("startMonth");
  const endInput = document.getElementById("endMonth");
  startInput.min = months[0];
  startInput.max = months[months.length - 1];
  endInput.min = months[0];
  endInput.max = months[months.length - 1];
  startInput.value = months[0];
  endInput.value = months[months.length - 1];
  state.startMonth = months[0];
  state.endMonth = months[months.length - 1];

  startInput.addEventListener("change", () => {
    state.startMonth = startInput.value;
    renderAll();
  });
  endInput.addEventListener("change", () => {
    state.endMonth = endInput.value;
    renderAll();
  });
  document.getElementById("resetDates").addEventListener("click", () => {
    startInput.value = months[0];
    endInput.value = months[months.length - 1];
    state.startMonth = months[0];
    state.endMonth = months[months.length - 1];
    renderAll();
  });
}

async function main() {
  try {
    state.data = await loadData();
    initFilters();
    renderAll();
    document.getElementById("dataStatus").textContent = `Generated ${new Date(state.data.summary.generated_at).toLocaleString()}`;
    document.querySelectorAll(".tab").forEach((button) => {
      button.addEventListener("click", () => setActiveTab(button.dataset.tab));
    });
  } catch (error) {
    document.getElementById("dataStatus").textContent = "Data failed to load";
    document.querySelector("main").innerHTML = `<div class="note-box danger"><h2>Unable to load dashboard data</h2><p>${error.message}</p></div>`;
    console.error(error);
  }
}

main();
