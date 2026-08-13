const fmt = new Intl.NumberFormat("en-US");
const pct = (v, digits = 1) => `${(v * 100).toFixed(digits)}%`;
const signedPct = (v, digits = 1) => `${v >= 0 ? "+" : ""}${pct(v, digits)}`;

const colors = {
  navy: "#123a60",
  blue: "#2f6df6",
  lightBlue: "#77a5cf",
  paleBlue: "#adc4d8",
  teal: "#18a6a0",
  green: "#2f8f57",
  gold: "#c99a2e",
  red: "#b9534f",
  grid: "#dfe7f1",
  text: "#34445b"
};

const $ = (id) => document.getElementById(id);

const GC_TRIAL_CONVERSIONS = [
  { label: "Jan", conversions: 2445 },
  { label: "Feb", conversions: 2707 },
  { label: "Mar", conversions: 4791 },
  { label: "Apr", conversions: 9694 },
  { label: "May", conversions: 10199 },
  { label: "Jun", conversions: 9716 },
  { label: "Jul", conversions: 9180 }
];

const defaultNarrative = {
  eyebrow: "USGA",
  reportMonth: "August 2026",
  reportDate: "Report Date: August 2, 2026",
  page1Title: "August GC Membership Report",
  page1Dek: "Monthly view of GC membership performance, acquisition, retention, and recovery.",
  activeKpiLabel: "Total Active GC Membership",
  netKpiLabel: "Net Membership Change July",
  ytdKpiLabel: "Net Membership Change YTD",
  annualKpiLabel: "12-Month YoY GC Change",
  trendLabel: "Year Over Year Growth",
  trendTitle: "Active GC Members By Year",
  trendNote: "Same month across years, back to 2022.",
  interpretationLabel: "What leadership should know",
  interpretationTitle: "Key Takeaways",
  movementLabel: "Membership Movement",
  movementTitle: "July Membership Reconciliation",
  movementNote: "What changed in July to reach the current membership total.",
  projectionLabel: "Year-End Outlook",
  projectionTitle: "2026 Year-End Projection",
  mixLabel: "Acquisition Mix",
  mixTitle: "Where New Members Came From",
  retentionLabel: "Retention + Recovery",
  retentionTitle: "Preserving Membership",
  renewalMiniLabel: "Renewal Rate",
  recoveredMiniLabel: "Recovered",
  retentionReadoutLabel: "Operating readout",
  footerLeft: "GC Membership Executive Report",

  page2Eyebrow: "How Membership Is Growing",
  page2Title: "GC Acquisition",
  page2Dek: "New Golfers measures newly created GHIN numbers in the GC club by source.",
  newMembersLabel: "New GC Golfers July",
  trialsLabel: "GHIN Trial Conversions",
  paidLabel: "Paid Media Conversions",
  acqTrendLabel: "Acquisition Trend",
  acqTrendTitle: "Monthly New Members",
  acqMixPageLabel: "Source Mix",
  acqMixPageTitle: "YTD Acquisition Mix",
  segmentLabel: "Segment Performance",
  segmentTitle: "Executive Source Readout",
  page2NotesLabel: "Executive Takeaway",

  page3Eyebrow: "How Membership Is Being Retained",
  page3Title: "GC Retention",
  page3Dek: "Retention measures renewal performance and membership durability within the GC club.",
  renewalPageLabel: "July On-Time Renewal Rate",
  retainedPageLabel: "Members Renewed",
  recoveryPageLabel: "Recovered Members",
  retentionTrendLabel: "Retention Trend",
  retentionTrendTitle: "On-Time Renewal Rate by Month",
  recoveryTrendLabel: "Recovery Trend",
  recoveryTrendTitle: "Monthly Recoveries",
  cohortLabel: "Cohort View",
  cohortTitle: "Retention by Member Tenure",
  page3NotesLabel: "What Leadership Should Know",

  page4Eyebrow: "How Membership Is Being Recovered",
  page4Title: "GC Recovery",
  page4Dek: "Recovery measures inactive GC club golfers who returned to active GC membership.",
  challengeTotalLabel: "Total Challenges",
  challengeGolfersLabel: "Total Golfers",
  rankedGolfersLabel: "Ranked Golfers",
  scoresPostedLabel: "Scores Posted",
  programTrendLabel: "Program Trend",
  programTrendTitle: "Growth Since May",
  challengeMixLabel: "Participation",
  challengeMixTitle: "Engagement Quality",
  agaLabel: "AGA Performance",
  agaTitle: "Top GHIN Challenge Associations",
  page4NotesLabel: "What Leadership Should Know",

  page5Eyebrow: "Analysis",
  page5Title: "What the Numbers Are Telling Us",
  page5Dek: "",
  opportunitiesLabel: "Opportunities",
  opportunitiesTitle: "Where momentum can be extended",
  concernsLabel: "Concerns",
  concernsTitle: "Where leadership attention is needed",
  actionsLabel: "Leadership Questions",
  actionsTitle: "Questions for the Next Review",
  decisionLabel: "Near-Term Watchout",
  decisionText: "Do not let strong total membership hide the acquisition slowdown. The report is positive overall, but new golfer growth needs attention.",

  interpretation: [null, null, null],
  page2Bullets: [
    "GHIN Trials remain the largest identified acquisition source and should be monitored as a conversion engine.",
    "Paid Media is material but currently only covers the approved paid media attribution source.",
    "Organic / Untagged remains large enough to require continued attribution cleanup."
  ],
  page3Bullets: [
    "Retention is the primary reason total membership remains strong despite softer acquisition.",
    "On-time renewal reached 83.4% in July, materially above last July's 66.0% rate.",
    "Cohort health remains strongest in newer member years and should be watched as cohorts mature."
  ],
  page4Bullets: [
    "Recovery added 39,664 members year to date and remains a visible contributor to active membership.",
    "July recoveries were lower than the March peak but still added 4,934 members to the active base.",
    "Club-level recovery performance can help identify repeatable reactivation patterns."
  ],
  opportunityBullets: [
    "Trial conversion engine generated the largest identified acquisition contribution.",
    "Membership momentum remains positive through the latest completed report month.",
    "Engagement expansion creates a broader activation story beyond acquisition."
  ],
  concernBullets: [
    "Organic / Untagged acquisition remains large and limits source accountability.",
    "Paid Media timing and coverage must be kept explicit in the executive report.",
    "Manual workstream commentary still requires owner validation before publication."
  ],
  actions: [
    { priority: "Acquisition", action: "Who owns the plan to address softer new golfer creation versus 2025?", owner: "Leadership", timing: "Next review" },
    { priority: "Story", action: "Are we telling the right story, to the right golfers, with a message that makes a Handicap Index feel worth having?", owner: "Marketing", timing: "Fall planning" },
    { priority: "Paid Media", action: "Are paid campaigns creating new interest, or mostly capturing golfers who were already likely to sign up?", owner: "Marketing / Analytics", timing: "Before budget review" },
    { priority: "Win-back", action: "What results would justify scaling expired-member outreach nationally?", owner: "Retention", timing: "After test" }
  ]
};

async function loadNarrative() {
  try {
    const key = new URLSearchParams(location.search).get("report") || "current";
    const archived = await loadArchivedCopy(key);
    const raw = localStorage.getItem(`gcExecutiveReportNarrative:${key}`) || localStorage.getItem("gcExecutiveReportNarrative");
    const draft = raw ? JSON.parse(raw) : {};
    const narrative = deepMerge(deepMerge(defaultNarrative, archived), draft);
    if (narrative.page5Title === "What the Results Suggest") {
      narrative.page5Title = "What the Numbers Are Telling Us";
    }
    if (narrative.page1Title === "August Membership Report" || narrative.page1Title === "Executive Membership Report") {
      narrative.page1Title = "August GC Membership Report";
    }
    if (narrative.eyebrow === "GC Membership") {
      narrative.eyebrow = "USGA";
    }
    if (narrative.page1Dek === "Monthly executive report summarizing GC membership performance, acquisition, retention, and recovery through the latest reporting period.") {
      narrative.page1Dek = "Monthly view of GC membership performance, acquisition, retention, and recovery.";
    }
    if (narrative.trendTitle === "Active Members by Year") {
      narrative.trendTitle = "Active GC Members By Year";
    }
    if (narrative.page2Dek === "New Golfers measures newly created GHIN numbers by source.") {
      narrative.page2Dek = "New Golfers measures newly created GHIN numbers in the GC club by source.";
    }
    if (narrative.page3Dek === "Retention measures renewal performance and durability across the active membership base.") {
      narrative.page3Dek = "Retention measures renewal performance and membership durability within the GC club.";
    }
    if (narrative.page4Dek === "Recovery measures inactive golfers who returned to active membership during the reporting period.") {
      narrative.page4Dek = "Recovery measures inactive GC club golfers who returned to active GC membership.";
    }
    if (narrative.activeKpiLabel === "Total Active Membership") {
      narrative.activeKpiLabel = "Total Active GC Membership";
    }
    if (narrative.netKpiLabel === "Net Membership Change") {
      narrative.netKpiLabel = "Net Membership Change July";
    }
    if (narrative.ytdKpiLabel === "Year-to-Date Growth" || narrative.ytdKpiLabel === "Year to Date GC Change") {
      narrative.ytdKpiLabel = "Net Membership Change YTD";
    }
    if (narrative.annualKpiLabel === "Twelve-Month Change") {
      narrative.annualKpiLabel = "12-Month YoY GC Change";
    }
    return narrative;
  } catch {
    return defaultNarrative;
  }
}

async function loadArchivedCopy(key) {
  if (!key || key === "current") {
    try {
      const manifest = await loadJson("../report-months.json");
      key = manifest.current;
    } catch {
      return {};
    }
  }
  try {
    return await loadJson(`../archive/${key}/report-copy.json`);
  } catch {
    return {};
  }
}

function deepMerge(base, override) {
  const out = { ...base, ...override };
  for (const key of Object.keys(base)) {
    if (Array.isArray(base[key])) out[key] = override?.[key] || base[key];
  }
  return out;
}

function applyCopy(narrative) {
  document.querySelectorAll("[data-copy]").forEach(el => {
    const key = el.dataset.copy;
    if (key === "page5Title") {
      el.textContent = "What the Numbers Are Telling Us";
      return;
    }
    if (narrative[key]) el.textContent = narrative[key];
  });
}

async function loadJson(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`Unable to load ${path}`);
  return res.json();
}

function latestActual(rows) {
  return [...rows].reverse().find(row => row.activeGolfers != null);
}

function setText(id, value) {
  const el = $(id);
  if (el) el.textContent = value;
}

function monthNameRange(lastMonth) {
  const names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  return `Jan-${names[lastMonth - 1]}`;
}

function drawLineChart(svg, values, labels, opts = {}) {
  if (!svg || !values.length) return;
  const w = 520, h = opts.height || 210;
  const pad = { left: 32, right: 18, top: 18, bottom: 34 };
  const minRaw = Math.min(...values);
  const maxRaw = Math.max(...values);
  const min = opts.zero ? 0 : minRaw * 0.985;
  const max = maxRaw * 1.08 || 1;
  const x = i => pad.left + (i / Math.max(values.length - 1, 1)) * (w - pad.left - pad.right);
  const y = v => pad.top + (1 - ((v - min) / (max - min))) * (h - pad.top - pad.bottom);
  const points = values.map((v, i) => [x(i), y(v)]);
  const line = points.map((p, i) => `${i ? "L" : "M"} ${p[0]} ${p[1]}`).join(" ");
  const area = `M ${points[0][0]} ${h - pad.bottom} ` + points.map(p => `L ${p[0]} ${p[1]}`).join(" ") + ` L ${points.at(-1)[0]} ${h - pad.bottom} Z`;
  svg.innerHTML = `
    <line x1="${pad.left}" y1="${h - pad.bottom}" x2="${w - pad.right}" y2="${h - pad.bottom}" stroke="${colors.grid}" stroke-width="2"/>
    <path d="${area}" fill="#dfeaff"/>
    <path d="${line}" fill="none" stroke="${opts.color || colors.blue}" stroke-width="4" stroke-linecap="round"/>
    ${points.map(p => `<circle cx="${p[0]}" cy="${p[1]}" r="5" fill="#fff" stroke="${opts.color || colors.blue}" stroke-width="3"/>`).join("")}
    ${labels.map((label, i) => `<text x="${x(i)}" y="${h - 10}" text-anchor="middle" fill="#667791" font-size="10">${label}</text>`).join("")}
  `;
}

function drawBarChart(svg, values, labels, opts = {}) {
  if (!svg || !values.length) return;
  const w = 520, h = 250;
  const pad = { left: 38, right: 18, top: 24, bottom: 38 };
  const max = Math.max(...values) * 1.18 || 1;
  const bw = (w - pad.left - pad.right) / values.length * 0.48;
  const gap = (w - pad.left - pad.right) / values.length;
  const y = v => pad.top + (1 - v / max) * (h - pad.top - pad.bottom);
  svg.innerHTML = `
    <line x1="${pad.left}" y1="${h - pad.bottom}" x2="${w - pad.right}" y2="${h - pad.bottom}" stroke="${colors.grid}" stroke-width="2"/>
    ${values.map((v, i) => {
      const x = pad.left + i * gap + gap / 2 - bw / 2;
      const barY = y(v);
      return `<rect x="${x}" y="${barY}" width="${bw}" height="${h - pad.bottom - barY}" rx="6" fill="${opts.color || colors.navy}"/>
        <text x="${x + bw / 2}" y="${barY - 8}" text-anchor="middle" fill="${colors.red}" font-size="11">${fmt.format(v)}</text>
        <text x="${x + bw / 2}" y="${h - 10}" text-anchor="middle" fill="#667791" font-size="10">${labels[i]}</text>`;
    }).join("")}
  `;
}

function drawRecoveryTrendChart(svg, rows, opts = {}) {
  if (!svg || !rows.length) return;
  const w = 760, h = 265;
  svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
  const pad = { left: 54, right: 28, top: 28, bottom: 38 };
  const values = rows.map(row => row.recoveries);
  const max = Math.ceil(Math.max(...values) / 4000) * 4000 || 12000;
  const ticks = [0, max / 3, max * 2 / 3, max];
  const plotW = w - pad.left - pad.right;
  const step = plotW / rows.length;
  const barW = Math.min(58, step * 0.42);
  const y = value => pad.top + (1 - value / max) * (h - pad.top - pad.bottom);
  const highlightMonth = opts.highlightMonth || rows.at(-1)?.month;
  svg.innerHTML = `
    <line x1="${pad.left}" y1="${pad.top}" x2="${pad.left}" y2="${h - pad.bottom}" stroke="#9aa8ba" stroke-width="1.6"/>
    ${ticks.map(tick => {
      const ty = y(tick);
      return `<line x1="${pad.left}" y1="${ty}" x2="${w - pad.right}" y2="${ty}" stroke="${tick === 0 ? "#9aa8ba" : colors.grid}" stroke-width="${tick === 0 ? 1.6 : 1}"/>
        <text x="${pad.left - 10}" y="${ty + 4}" text-anchor="end" fill="#596b84" font-size="11" font-weight="700">${tick ? `${Math.round(tick / 1000)}K` : "0"}</text>`;
    }).join("")}
    ${rows.map((row, i) => {
      const value = row.recoveries;
      const x = pad.left + i * step + step / 2 - barW / 2;
      const barY = y(value);
      const isHighlight = row.month === highlightMonth || i === rows.length - 1;
      const fill = isHighlight ? "#1f7a4d" : colors.green;
      return `<rect x="${x}" y="${barY}" width="${barW}" height="${h - pad.bottom - barY}" rx="7" fill="${fill}"/>
        <text x="${x + barW / 2}" y="${barY - 10}" text-anchor="middle" fill="${isHighlight ? colors.green : colors.red}" font-size="12" font-weight="800">${fmt.format(value)}</text>
        ${isHighlight ? `<rect x="${x + 5}" y="${barY + 13}" width="${barW - 10}" height="20" rx="10" fill="#fff" stroke="#b8c8d9" stroke-width="1.4"/>
          <text x="${x + barW / 2}" y="${barY + 27}" text-anchor="middle" fill="#29415e" font-size="9.5" font-weight="800">July</text>` : ""}
        <text x="${x + barW / 2}" y="${h - 12}" text-anchor="middle" fill="#596b84" font-size="11" font-weight="700">${row.month.slice(0, 3)}</text>`;
    }).join("")}
  `;
}

function drawRecoveryComparisonChart(svg, series2025, series2026, opts = {}) {
  if (!svg) return;
  const w = 760, h = 340;
  svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
  const pad = { left: 54, right: 58, top: 28, bottom: 38 };
  const values = [...series2025, ...series2026].map(row => row.value).filter(value => Number.isFinite(value));
  const max = opts.max || Math.ceil(Math.max(...values, 1) / opts.tickStep) * opts.tickStep;
  const ticks = opts.ticks || Array.from({ length: 5 }, (_, i) => i * max / 4);
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const plotW = w - pad.left - pad.right;
  const plotH = h - pad.top - pad.bottom;
  const x = monthNum => pad.left + ((monthNum - 1) / 11) * plotW;
  const y = value => pad.top + (1 - value / max) * plotH;
  const formatAxis = value => opts.axisFormat ? opts.axisFormat(value) : fmt.format(value);
  const formatPoint = value => opts.pointFormat ? opts.pointFormat(value) : fmt.format(value);
  const linePath = rows => rows
    .filter(row => Number.isFinite(row.value))
    .map((row, index) => `${index ? "L" : "M"} ${x(row.monthNum)} ${y(row.value)}`)
    .join(" ");
  const points = (rows, color) => rows
    .filter(row => Number.isFinite(row.value))
    .map(row => `<circle cx="${x(row.monthNum)}" cy="${y(row.value)}" r="5.2" fill="#fff" stroke="${color}" stroke-width="2.4"/>`)
    .join("");
  const latest = [...series2026].reverse().find(row => Number.isFinite(row.value));
  const latestX = x(latest.monthNum);
  const latestY = y(latest.value);
  svg.innerHTML = `
    <line x1="${pad.left}" y1="${pad.top}" x2="${pad.left}" y2="${h - pad.bottom}" stroke="#9aa8ba" stroke-width="1.4"/>
    ${ticks.map(tick => {
      const ty = y(tick);
      return `<line x1="${pad.left}" y1="${ty}" x2="${w - pad.right}" y2="${ty}" stroke="${tick === 0 ? "#9aa8ba" : colors.grid}" stroke-width="${tick === 0 ? 1.4 : 1}"/>
        <text x="${pad.left - 10}" y="${ty + 5}" text-anchor="end" fill="#596b84" font-size="13" font-weight="800">${formatAxis(tick)}</text>`;
    }).join("")}
    <path d="${linePath(series2025)}" fill="none" stroke="${colors.gold}" stroke-width="3.2"/>
    <path d="${linePath(series2026)}" fill="none" stroke="${colors.red}" stroke-width="3.4"/>
    ${points(series2025, colors.gold)}
    ${points(series2026, colors.red)}
    <circle cx="${latestX}" cy="${latestY}" r="10" fill="none" stroke="${colors.red}" stroke-width="2.2" stroke-dasharray="4 4"/>
    ${opts.callout ? `<path d="M ${latestX - 7} ${latestY - 7} L ${latestX - 68} ${latestY - 60}" fill="none" stroke="${colors.red}" stroke-width="1.8"/>
      <text x="${latestX - 70}" y="${latestY - 64}" text-anchor="middle" fill="${colors.red}" font-size="14" font-weight="900">${opts.callout}</text>` : ""}
    ${months.map((month, index) => `<text x="${x(index + 1)}" y="${h - 11}" text-anchor="middle" fill="#596b84" font-size="12.5" font-weight="800">${month}</text>`).join("")}
    <g transform="translate(${w - 58},${pad.top - 10})">
      <line x1="-31" y1="0" x2="-12" y2="0" stroke="${colors.gold}" stroke-width="3.2"/><circle cx="-21" cy="0" r="4.8" fill="#fff" stroke="${colors.gold}" stroke-width="2.3"/>
      <text x="0" y="5" fill="${colors.text}" font-size="12.5" font-weight="900">2025</text>
      <line x1="-31" y1="25" x2="-12" y2="25" stroke="${colors.red}" stroke-width="3.2"/><circle cx="-21" cy="25" r="4.8" fill="#fff" stroke="${colors.red}" stroke-width="2.3"/>
      <text x="0" y="30" fill="${colors.text}" font-size="12.5" font-weight="900">2026</text>
    </g>
  `;
}

function drawYoYMembershipChart(svg, rows) {
  if (!svg || !rows.length) return;
  const w = 520, h = 360;
  svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
  const pad = { left: 54, right: 20, top: 24, bottom: 44 };
  const max = Math.max(...rows.map(row => row.activeGolfers)) * 1.04;
  const y = v => pad.top + (1 - v / max) * (h - pad.top - pad.bottom);
  const plotW = w - pad.left - pad.right;
  const step = plotW / rows.length;
  const barW = 66;
  const ticks = [0, 100000, 200000, 300000, 400000, 500000];
  svg.innerHTML = `
    ${ticks.map(t => {
      const ty = y(t);
      return `<line x1="${pad.left}" y1="${ty}" x2="${w - pad.right}" y2="${ty}" stroke="${colors.grid}" stroke-width="1.5"/>
        <text x="${pad.left - 8}" y="${ty + 4}" text-anchor="end" fill="#667791" font-size="11">${t ? `${Math.round(t / 1000)}K` : "0"}</text>`;
    }).join("")}
    ${rows.map((row, i) => {
      const x = pad.left + i * step + step / 2 - barW / 2;
      const barY = y(row.activeGolfers);
      const isCurrent = i === rows.length - 1;
      const prev = i ? rows[i - 1].activeGolfers : null;
      const growth = prev ? pct((row.activeGolfers - prev) / prev) : "";
      return `<rect x="${x}" y="${barY}" width="${barW}" height="${h - pad.bottom - barY}" rx="8" fill="${isCurrent ? colors.red : colors.paleBlue}"/>
        <text x="${x + barW / 2}" y="${barY - 10}" text-anchor="middle" fill="${colors.text}" font-size="14">${Math.round(row.activeGolfers / 1000)}K</text>
        ${growth ? `<rect x="${x + 4}" y="${barY + 15}" width="${barW - 8}" height="20" rx="10" fill="#fff" stroke="#c8d5e4" stroke-width="1.5"/>
          <text x="${x + barW / 2}" y="${barY + 29}" text-anchor="middle" fill="#44546a" font-size="10">${growth}</text>` : ""}
        <text x="${x + barW / 2}" y="${h - 11}" text-anchor="middle" fill="#667791" font-size="13" font-weight="700">${row.month.slice(0, 3)} '${String(row.year).slice(2)}</text>`;
    }).join("")}
  `;
}

function drawCumulativeAcquisitionChart(svg, rows, currentYear, currentMonth) {
  if (!svg || !rows.length) return;
  const yearly = [...new Set(rows.map(row => row.year))]
    .sort()
    .map(year => {
      const total = rows
        .filter(row => row.year === year && row.monthNum <= currentMonth && row.newGolfers != null)
        .reduce((sum, row) => sum + row.newGolfers, 0);
      return { year, total };
    })
    .filter(row => row.total > 0);
  const w = 680, h = 430;
  svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
  const pad = { left: 62, right: 18, top: 10, bottom: 58 };
  const maxValue = Math.max(...yearly.map(row => row.total));
  const max = Math.max(200000, Math.ceil(maxValue / 50000) * 50000);
  const y = v => pad.top + (1 - v / max) * (h - pad.top - pad.bottom);
  const plotW = w - pad.left - pad.right;
  const step = plotW / yearly.length;
  const barW = 78;
  const ticks = Array.from({ length: 6 }, (_, i) => (max / 5) * i);
  svg.innerHTML = `
    ${ticks.map(t => `<line x1="${pad.left}" y1="${y(t)}" x2="${w - pad.right}" y2="${y(t)}" stroke="${colors.grid}" stroke-width="1.2"/>
      <text x="${pad.left - 12}" y="${y(t) + 6}" text-anchor="end" fill="#667791" font-size="15">${t ? `${Math.round(t / 1000)}K` : "0"}</text>`).join("")}
    <line x1="${pad.left}" y1="${pad.top}" x2="${pad.left}" y2="${h - pad.bottom}" stroke="#9aabba" stroke-width="1.8"/>
    <line x1="${pad.left}" y1="${h - pad.bottom}" x2="${w - pad.right}" y2="${h - pad.bottom}" stroke="#9aabba" stroke-width="1.8"/>
    ${yearly.map((row, i) => {
      const x = pad.left + i * step + step / 2 - barW / 2;
      const barY = y(row.total);
      const isCurrent = row.year === currentYear;
      const prev = i ? yearly[i - 1].total : null;
      const growth = prev ? pct((row.total - prev) / prev) : "";
      return `<rect x="${x}" y="${barY}" width="${barW}" height="${h - pad.bottom - barY}" rx="8" fill="${isCurrent ? colors.red : colors.paleBlue}"/>
        <text x="${x + barW / 2}" y="${barY - 11}" text-anchor="middle" fill="${colors.text}" font-size="18">${Math.round(row.total / 1000)}K</text>
        ${growth ? `<rect x="${x + 5}" y="${barY + 15}" width="${barW - 10}" height="22" rx="11" fill="#fff" stroke="#c8d5e4" stroke-width="1.5"/>
          <text x="${x + barW / 2}" y="${barY + 30}" text-anchor="middle" fill="#44546a" font-size="12">${growth}</text>` : ""}
        <text x="${x + barW / 2}" y="${h - 36}" text-anchor="middle" fill="#667791" font-size="16">
          <tspan x="${x + barW / 2}" dy="0">Jan-Jul</tspan>
          <tspan x="${x + barW / 2}" dy="18">'${String(row.year).slice(2)}</tspan>
        </text>`;
    }).join("")}
  `;
}

function drawStackedSourceChart(svg, rows) {
  if (!svg || !rows.length) return;
  const w = 680, h = 280;
  svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
  const pad = { left: 52, right: 24, top: 24, bottom: 38 };
  const max = 30000;
  const xStep = (w - pad.left - pad.right) / rows.length;
  const barW = xStep * 0.52;
  const y = v => pad.top + (1 - v / max) * (h - pad.top - pad.bottom);
  const series = [
    { key: "trials", color: colors.navy },
    { key: "paid", color: colors.lightBlue },
    { key: "organic", color: colors.paleBlue }
  ];
  const ticks = [0, 15000, 30000];
  svg.innerHTML = `
    ${ticks.map(t => `<line x1="${pad.left}" y1="${y(t)}" x2="${w - pad.right}" y2="${y(t)}" stroke="${colors.grid}" stroke-width="1.2"/>
      <text x="${pad.left - 8}" y="${y(t) + 4}" text-anchor="end" fill="#667791" font-size="10">${t ? fmt.format(t) : "0"}</text>`).join("")}
    ${rows.map((row, i) => {
      const x = pad.left + i * xStep + xStep / 2 - barW / 2;
      let base = 0;
      const rects = series.map(item => {
        const value = row[item.key] || 0;
        const top = base + value;
        const rectY = y(top);
        const height = y(base) - rectY;
        base = top;
        const label = height > 16 && value ? `<text x="${x + barW / 2}" y="${rectY + height / 2 + 4}" text-anchor="middle" fill="${item.key === "organic" ? colors.text : "#fff"}" font-size="9">${fmt.format(value)}</text>` : "";
        return `<rect x="${x}" y="${rectY}" width="${barW}" height="${height}" fill="${item.color}"/>${label}`;
      }).join("");
      return `${rects}
        <text x="${x + barW / 2}" y="${y(row.total) - 8}" text-anchor="middle" fill="${colors.text}" font-size="11">${fmt.format(row.total)}</text>
        <text x="${x + barW / 2}" y="${h - 10}" text-anchor="middle" fill="#667791" font-size="10">${row.month}</text>`;
    }).join("")}
  `;
}

function drawRetentionTrendChart(svg, rows) {
  if (!svg || !rows.length) return;
  const values = rows.map(row => row.onTimeRenewalRate || 0);
  const labels = rows.map(row => row.month.slice(0, 3));
  const w = 620, h = 320;
  svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
  const pad = { left: 62, right: 28, top: 24, bottom: 48 };
  const ticks = [0.6, 0.7, 0.8, 0.9];
  const min = 0.6;
  const max = 0.9;
  const x = i => pad.left + (i / Math.max(values.length - 1, 1)) * (w - pad.left - pad.right);
  const y = v => pad.top + (1 - ((v - min) / (max - min))) * (h - pad.top - pad.bottom);
  const points = values.map((v, i) => [x(i), y(v)]);
  const line = points.map((p, i) => `${i ? "L" : "M"} ${p[0]} ${p[1]}`).join(" ");
  const area = `M ${points[0][0]} ${h - pad.bottom} ` + points.map(p => `L ${p[0]} ${p[1]}`).join(" ") + ` L ${points.at(-1)[0]} ${h - pad.bottom} Z`;
  svg.innerHTML = `
    ${ticks.map(t => `<line x1="${pad.left}" y1="${y(t)}" x2="${w - pad.right}" y2="${y(t)}" stroke="${colors.grid}" stroke-width="1.2"/>
      <text x="${pad.left - 12}" y="${y(t) + 5}" text-anchor="end" fill="#667791" font-size="13">${pct(t)}</text>`).join("")}
    <line x1="${pad.left}" y1="${pad.top}" x2="${pad.left}" y2="${h - pad.bottom}" stroke="#9aabba" stroke-width="1.8"/>
    <line x1="${pad.left}" y1="${h - pad.bottom}" x2="${w - pad.right}" y2="${h - pad.bottom}" stroke="#9aabba" stroke-width="1.8"/>
    <path d="${area}" fill="#dff4f3"/>
    <path d="${line}" fill="none" stroke="${colors.teal}" stroke-width="4.5" stroke-linecap="round"/>
    ${points.map((p, i) => `<circle cx="${p[0]}" cy="${p[1]}" r="6" fill="#fff" stroke="${colors.teal}" stroke-width="3"/>
      <text x="${p[0]}" y="${p[1] - 13}" text-anchor="middle" fill="${colors.text}" font-size="13">${pct(values[i])}</text>`).join("")}
    ${labels.map((label, i) => `<text x="${x(i)}" y="${h - 14}" text-anchor="middle" fill="#667791" font-size="13">${label}</text>`).join("")}
  `;
}

function drawRetentionComparisonChart(svg, rows, metric, opts = {}) {
  if (!svg || !rows.length) return;
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const currentYear = opts.currentYear;
  const years = [currentYear - 1, currentYear];
  const series = years.map(year => ({
    year,
    color: year === currentYear ? colors.red : "#d9a100",
    values: months.map((_, i) => {
      const row = rows.find(item => item.year === year && item.monthNum === i + 1);
      return row?.[metric] ?? null;
    })
  }));
  const visibleValues = series.flatMap(row => row.values.filter(v => v != null));
  const minRaw = Math.min(...visibleValues);
  const maxRaw = Math.max(...visibleValues);
  const min = Math.floor((minRaw - 0.025) * 20) / 20;
  const max = Math.ceil((maxRaw + 0.025) * 20) / 20;
  const w = 760, h = 260;
  svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
  const pad = { left: 58, right: 88, top: 20, bottom: 38 };
  const x = i => pad.left + (i / 11) * (w - pad.left - pad.right);
  const y = v => pad.top + (1 - ((v - min) / (max - min))) * (h - pad.top - pad.bottom);
  const highlightMonth = opts.highlightMonth ?? 7;
  const highlightRow = rows.find(item => item.year === currentYear && item.monthNum === highlightMonth);
  const highlightValue = highlightRow?.[metric] ?? null;
  const highlightX = highlightValue == null ? null : x(highlightMonth - 1);
  const highlightY = highlightValue == null ? null : y(highlightValue);
  const ticks = Array.from({ length: 5 }, (_, i) => min + ((max - min) / 4) * i);
  const path = points => points.map((p, i) => `${i ? "L" : "M"} ${p[0]} ${p[1]}`).join(" ");
  svg.innerHTML = `
    ${ticks.map(t => `<line x1="${pad.left}" y1="${y(t)}" x2="${w - pad.right}" y2="${y(t)}" stroke="${colors.grid}" stroke-width="1.1"/>
      <text x="${pad.left - 10}" y="${y(t) + 5}" text-anchor="end" fill="#667791" font-size="12">${pct(t)}</text>`).join("")}
    <line x1="${pad.left}" y1="${pad.top}" x2="${pad.left}" y2="${h - pad.bottom}" stroke="#9aabba" stroke-width="1.7"/>
    <line x1="${pad.left}" y1="${h - pad.bottom}" x2="${w - pad.right}" y2="${h - pad.bottom}" stroke="#9aabba" stroke-width="1.7"/>
    ${months.map((m, i) => `<text x="${x(i)}" y="${h - 10}" text-anchor="middle" fill="#667791" font-size="11">${m}</text>`).join("")}
    ${series.map(row => {
      const points = row.values.map((v, i) => v == null ? null : [x(i), y(v)]).filter(Boolean);
      return `<path d="${path(points)}" fill="none" stroke="${row.color}" stroke-width="3.2" stroke-linecap="round"/>
        ${points.map(p => `<circle cx="${p[0]}" cy="${p[1]}" r="4" fill="#fff" stroke="${row.color}" stroke-width="2.2"/>`).join("")}
        <circle cx="${w - 74}" cy="${pad.top + (row.year === currentYear ? 18 : 0)}" r="4" fill="#fff" stroke="${row.color}" stroke-width="2"/>
        <text x="${w - 62}" y="${pad.top + 4 + (row.year === currentYear ? 18 : 0)}" fill="${colors.text}" font-size="12">${row.year}</text>`;
    }).join("")}
    ${highlightValue == null ? "" : `
      <circle cx="${highlightX}" cy="${highlightY}" r="8" fill="#fff" stroke="${colors.red}" stroke-width="3"/>
      <rect x="${highlightX + 12}" y="${highlightY - 18}" width="58" height="25" rx="12" fill="#fff" stroke="#c8d5e4" stroke-width="1.5"/>
      <text x="${highlightX + 41}" y="${highlightY - 1}" text-anchor="middle" fill="${colors.text}" font-size="13">${pct(highlightValue)}</text>
    `}
  `;
}

function drawProjectionChart(svg, rows, currentYear, currentMonth, growthRate) {
  if (!svg || !rows.length) return;
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const years = [...new Set(rows.map(row => row.year))].sort();
  const w = 680, h = 280;
  svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
  const pad = { left: 45, right: 62, top: 14, bottom: 30 };
  const monthValue = (year, monthNum) => {
    const row = rows.find(item => item.year === year && item.monthNum === monthNum);
    if (!row) return null;
    if (year === currentYear && row.activeGolfers == null) {
      const prior = rows.find(item => item.year === currentYear - 1 && item.monthNum === monthNum);
      return prior?.activeGolfers ? Math.round(prior.activeGolfers * (1 + growthRate)) : null;
    }
    return row.activeGolfers;
  };
  const series = years.map(year => ({
    year,
    values: months.map((_, i) => monthValue(year, i + 1)).filter(v => v != null)
  })).filter(row => row.values.length);
  const max = Math.max(...series.flatMap(row => row.values)) * 1.08;
  const x = i => pad.left + (i / 11) * (w - pad.left - pad.right);
  const y = v => pad.top + (1 - v / max) * (h - pad.top - pad.bottom);
  const palette = ["#aa6c74", "#4dbd64", "#6ca0d3", "#172235", colors.red];
  const ticks = [0, 150000, 300000, 450000, 600000];
  svg.innerHTML = `
    ${ticks.map(t => `<line x1="${pad.left}" y1="${y(t)}" x2="${w - pad.right}" y2="${y(t)}" stroke="${colors.grid}" stroke-width="1"/>
      <text x="${pad.left - 7}" y="${y(t) + 4}" text-anchor="end" fill="#667791" font-size="10">${t ? `${Math.round(t / 1000)}K` : "0"}</text>`).join("")}
    ${months.map((m, i) => `<text x="${x(i)}" y="${h - 8}" text-anchor="middle" fill="#667791" font-size="10">${m}</text>`).join("")}
    ${series.map((row, si) => {
      const isCurrent = row.year === currentYear;
      const points = row.values.map((v, i) => [x(i), y(v)]);
      const actualPoints = points.slice(0, isCurrent ? currentMonth : points.length);
      const projectedPoints = isCurrent ? points.slice(currentMonth - 1) : [];
      const path = pts => pts.map((p, i) => `${i ? "L" : "M"} ${p[0]} ${p[1]}`).join(" ");
      const labelIndex = Math.min(row.values.length - 1, 3);
      const labelX = x(labelIndex) + (isCurrent ? -10 : 8);
      const labelY = points[labelIndex][1] - (isCurrent ? 16 : 8);
      return `
        <path d="${path(actualPoints)}" fill="none" stroke="${palette[si]}" stroke-width="${isCurrent ? 4 : 2}" stroke-linecap="round"/>
        ${projectedPoints.length > 1 ? `<path d="${path(projectedPoints)}" fill="none" stroke="${palette[si]}" stroke-width="4" stroke-linecap="round" stroke-dasharray="7 6"/>` : ""}
        ${points.map((p, i) => `<circle cx="${p[0]}" cy="${p[1]}" r="${isCurrent ? 4 : 3}" fill="#fff" stroke="${palette[si]}" stroke-width="2"/>`).join("")}
        <text x="${w - 52}" y="${points.at(-1)[1] + 4}" fill="${colors.text}" font-size="12">${Math.round(row.values.at(-1) / 1000)}K</text>
        <text x="${labelX}" y="${labelY}" fill="${colors.text}" font-size="11">${row.year}${isCurrent ? " projected" : ""}</text>`;
    }).join("")}
  `;
}

function drawDonut(svg, items) {
  if (!svg) return;
  const cx = 130, cy = 130, r = 92, stroke = 44;
  const total = items.reduce((sum, item) => sum + item.value, 0);
  let acc = -90;
  const arcs = items.map(item => {
    const sweep = (item.value / total) * 360;
    const start = polar(cx, cy, r, acc);
    const end = polar(cx, cy, r, acc + sweep);
    const large = sweep > 180 ? 1 : 0;
    acc += sweep;
    return `<path d="M ${start.x} ${start.y} A ${r} ${r} 0 ${large} 1 ${end.x} ${end.y}" fill="none" stroke="${item.color}" stroke-width="${stroke}" stroke-linecap="butt"/>`;
  }).join("");
  svg.innerHTML = `${arcs}
    <circle cx="${cx}" cy="${cy}" r="52" fill="#fff"/>
    <text x="${cx}" y="${cy - 9}" text-anchor="middle" fill="${colors.navy}" font-size="20">${fmt.format(total)}</text>
    <text x="${cx}" y="${cy + 13}" text-anchor="middle" fill="${colors.navy}" font-size="10">YTD NEW GOLFERS</text>
    <text x="41" y="104" text-anchor="middle" fill="#102036" font-size="12">Organic</text>
    <text x="41" y="122" text-anchor="middle" fill="#102036" font-size="15">38%</text>
    <text x="111" y="217" text-anchor="middle" fill="#fff" font-size="12">Paid Media</text>
    <text x="111" y="235" text-anchor="middle" fill="#fff" font-size="16">16%</text>
    <text x="221" y="114" text-anchor="middle" fill="#fff" font-size="12">Trials</text>
    <text x="221" y="132" text-anchor="middle" fill="#fff" font-size="15">46%</text>`;
}

function polar(cx, cy, r, deg) {
  const rad = (deg - 90) * Math.PI / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

function bridgeCard(value, label, color) {
  return `<div class="bridge-card" style="background:${color}"><strong>${value}</strong><span>${label}</span></div>`;
}

function renderBridge(data) {
  $("bridge").innerHTML = [
    bridgeCard(fmt.format(data.opening), "Opening", colors.navy),
    `<div class="bridge-arrow">→</div>`,
    bridgeCard(`+${fmt.format(data.acquired)}`, "Acquired", colors.teal),
    `<div class="bridge-arrow">→</div>`,
    bridgeCard(`-${fmt.format(data.lost)}`, "Lost", colors.red),
    `<div class="bridge-arrow">→</div>`,
    bridgeCard(`+${fmt.format(data.recovered)}`, "Recovered", colors.green),
    `<div class="bridge-arrow">→</div>`,
    bridgeCard(fmt.format(data.closing), "Closing", colors.blue)
  ].join("");
}

function renderList(id, items) {
  const el = $(id);
  if (!el) return;
  el.innerHTML = items.map(item => `<li>${item}</li>`).join("");
}

function renderTakeaways(id, items) {
  const el = $(id);
  if (!el) return;
  el.innerHTML = items.map(item => `<li><strong>${item.title}</strong>${item.body}</li>`).join("");
}

function renderMiniBars(id, rows) {
  const el = $(id);
  if (!el || !rows.length) return;
  const max = Math.max(...rows.map(row => row.recoveriesYTD), 1);
  el.innerHTML = rows.map(row => `
    <div class="mini-bar-row">
      <span>${row.creationYear}</span>
      <div class="mini-bar-track"><i style="width:${Math.max(2, row.recoveriesYTD / max * 100)}%"></i></div>
      <strong>${fmt.format(row.recoveriesYTD)} <em>(${pct(row.shareOfYTDRecoveries)})</em></strong>
    </div>
  `).join("");
}

function renderNumberList(id, items) {
  const el = $(id);
  if (!el) return;
  el.innerHTML = items.map((item, i) => `<li><span>${String(i + 1).padStart(2, "0")}</span><p>${item}</p></li>`).join("");
}

function renderActions(items) {
  if (!$("actionsTable")) return;
  $("actionsTable").innerHTML = items.map(row => `<tr><td>${row.priority}</td><td>${row.action}</td><td>${row.owner}</td><td>${row.timing}</td></tr>`).join("");
}

async function render() {
  const narrative = await loadNarrative();
  const [membership, ghin, marketing, recovery, cohorts] = await Promise.all([
    loadJson("../../data/membership_monthly.json"),
    loadJson("../../data/ghin_trials.json"),
    loadJson("../../data/marketing_analysis.json"),
    loadJson("../../data/recovery_analysis.json"),
    loadJson("../../data/retention_cohorts.json")
  ]);

  applyCopy(narrative);
  const current = latestActual(membership);
  const prior = membership.find(row => row.year === current.year && row.monthNum === current.monthNum - 1);
  const dec = membership.find(row => row.year === current.year - 1 && row.monthNum === 12);
  const priorYear = membership.find(row => row.year === current.year - 1 && row.monthNum === current.monthNum);
  const ytdRows = membership.filter(row => row.year === current.year && row.monthNum <= current.monthNum && row.newGolfers != null);
  const ytdNew = ytdRows.reduce((sum, row) => sum + (row.newGolfers || 0), 0);
  const ytdGrowth = current.activeGolfers - dec.activeGolfers;
  const annualGrowth = (current.activeGolfers - priorYear.activeGolfers) / priorYear.activeGolfers;
  const recovered = recovery.summary.latestMonthRecoveries;
  const lost = prior.activeGolfers + current.newGolfers + recovered - current.activeGolfers;
  const paidMedia = marketing.monthlyPerformance.find(row => row.month === "YTD").conversions;
  const trials = GC_TRIAL_CONVERSIONS.reduce((sum, row) => sum + row.conversions, 0);
  const organic = ytdNew - trials - paidMedia;
  const mix = [
    { label: "GHIN Trials", value: trials, color: colors.navy },
    { label: "Paid Media", value: paidMedia, color: colors.lightBlue },
    { label: "Organic / Untagged", value: organic, color: colors.paleBlue }
  ];

  setText("activeMembers", fmt.format(current.activeGolfers));
  setText("activeSub", `${pct(current.percentChange)} vs prior month`);
  setText("netChange", `+${fmt.format(current.netChange)}`);
  setText("netSub", `${current.month} net active members`);
  setText("ytdGrowth", `+${fmt.format(ytdGrowth)}`);
  setText("ytdSub", `+${pct(ytdGrowth / dec.activeGolfers)} vs December`);
  setText("annualChange", `+${pct(annualGrowth)}`);
  setText("annualSub", `vs ${priorYear.month} ${priorYear.year}`);

  const trendRows = membership.filter(row => row.monthNum === current.monthNum && row.activeGolfers != null);
  drawYoYMembershipChart($("membershipTrend"), trendRows);
  const projectedDecember = Math.round(membership.find(row => row.year === current.year - 1 && row.monthNum === 12).activeGolfers * (1 + annualGrowth));
  setText("projectionValue", fmt.format(projectedDecember));
  setText("projectionSub", `${pct(annualGrowth)} growth scenario projected by EOY`);
  setText("projectionNote", `Actuals through ${current.month}. Projection assumes current YoY growth continues.`);
  drawProjectionChart($("projectionChart"), membership.filter(row => row.year >= 2022 && row.year <= current.year), current.year, current.monthNum, annualGrowth);
  renderBridge({ opening: prior.activeGolfers, acquired: current.newGolfers, lost, recovered, closing: current.activeGolfers });
  renderInterpretation(narrative, current, recovered, lost, organic);
  renderSourceMixCards("sourceMixCards", mix, ytdNew);

  setText("newMembers", fmt.format(current.newGolfers));
  const priorYearYtdRows = membership.filter(row => row.year === current.year - 1 && row.monthNum <= current.monthNum && row.newGolfers != null);
  const priorYearYtdNew = priorYearYtdRows.reduce((sum, row) => sum + (row.newGolfers || 0), 0);
  const priorYearSameMonth = membership.find(row => row.year === current.year - 1 && row.monthNum === current.monthNum);
  const ytdActiveShare = ytdNew / current.activeGolfers;
  const priorYtdActiveShare = priorYearYtdNew / priorYear.activeGolfers;
  setText("newMembersDelta", `${pct((current.newGolfers - priorYearSameMonth.newGolfers) / priorYearSameMonth.newGolfers)} vs ${current.month} ${priorYearSameMonth.year}`);
  setText("newMembersSub", `${current.month} ${current.year}`);
  setText("newMembersYtd", fmt.format(ytdNew));
  setText("newMembersYtdDelta", `${pct((ytdNew - priorYearYtdNew) / priorYearYtdNew)} vs Jan-July ${priorYear.year}`);
  setText("newGolfersYoyChange", pct((ytdNew - priorYearYtdNew) / priorYearYtdNew));
  setText("newGolfersYoyDelta", `${fmt.format(ytdNew - priorYearYtdNew)} golfers vs Jan-July ${priorYear.year}`);
  setText("trialConversions", fmt.format(trials));
  setText("paidConversions", fmt.format(paidMedia));
  const monthlySources = ytdRows.map(row => {
    const shortMonth = row.month.slice(0, 3);
    const trialsMonth = GC_TRIAL_CONVERSIONS.find(item => item.label === shortMonth)?.conversions || 0;
    const paidMonth = marketing.monthlyPerformance.find(item => item.month === shortMonth)?.conversions || 0;
    const organicMonth = Math.max((row.newGolfers || 0) - trialsMonth - paidMonth, 0);
    return { month: shortMonth, trials: trialsMonth, paid: paidMonth, organic: organicMonth, total: row.newGolfers || 0 };
  });
  const latestSourceMonth = monthlySources.at(-1);
  renderTakeaways("page2Summary", [
    {
      title: "Acquisition trend is concerning",
      body: `YTD new GHIN numbers are down ${pct((ytdNew - priorYearYtdNew) / priorYearYtdNew)} versus Jan-July ${priorYear.year}, and ${current.month} was down ${pct((current.newGolfers - priorYearSameMonth.newGolfers) / priorYearSameMonth.newGolfers)} versus last year.`
    },
    {
      title: "GHIN Trials are a healthy acquisition source",
      body: `GC Trial Conversions account for ${pct(trials / ytdNew)} of year-to-date new golfers, which is a meaningful share of total GC acquisition.`
    },
    {
      title: "Retention is backstopping growth",
      body: `Despite softer acquisition, active membership remains up because renewal performance and retained members are carrying more of the growth load.`
    }
  ]);
  drawCumulativeAcquisitionChart($("acqYoyBars"), membership, current.year, current.monthNum);
  drawStackedSourceChart($("sourceTrendBars"), monthlySources);
  renderLegend("sourceTrendLegend", [
    { label: "GHIN Trials", color: colors.navy },
    { label: "Paid Media", color: colors.lightBlue },
    { label: "Organic / Untagged", color: colors.paleBlue }
  ]);

  const priorYearRetention = membership.find(row => row.year === current.year - 1 && row.monthNum === current.monthNum);
  const activeToday = cohorts.summary.find(row => row.label === "Active Today");
  const inactiveToday = cohorts.summary.find(row => row.label === "Inactive Today");
  setText("renewalRatePage", pct(current.onTimeRenewalRate));
  setText("renewalRateSub", `vs ${pct(priorYearRetention.onTimeRenewalRate)} last ${current.month}`);
  setText("rollingRetentionPage", pct(current.retentionRate));
  setText("rollingRetentionSub", `vs ${pct(priorYearRetention.retentionRate)} last ${current.month}`);
  setText("activeTodayPage", activeToday.valueDisplay);
  setText("activeTodaySub", activeToday.subDisplay);
  setText("inactiveTodayPage", inactiveToday.valueDisplay);
  setText("inactiveTodaySub", inactiveToday.subDisplay);
  setText("membersRetained", fmt.format(current.renewed));
  const activeBeyond13 = cohorts.summary.find(row => row.label === "Active Beyond 13 Months");
  const activeBeyond25 = cohorts.summary.find(row => row.label === "Active Beyond 25 Months");
  const activeBeyond37 = cohorts.summary.find(row => row.label === "Active Beyond 37 Months");
  setText("activeBeyond13", activeBeyond13.valueDisplay);
  drawRetentionComparisonChart($("retentionTrend"), membership, "onTimeRenewalRate", { currentYear: current.year, highlightMonth: current.monthNum });
  drawRetentionComparisonChart($("rollingRetentionTrend"), membership, "retentionRate", { currentYear: current.year, highlightMonth: current.monthNum });
  setText("page3TakeawayText", `Retention is up significantly following the May auto-renewal changes, with ${current.month} on-time renewal at ${pct(current.onTimeRenewalRate)} versus ${pct(priorYearRetention.onTimeRenewalRate)} last ${current.month}. That retention lift is a major reason year-to-date membership growth remains strong despite softer acquisition.`);

  setText("recoveryYtd", fmt.format(recovery.summary.recoveriesYTD));
  setText("recoveryLatest", fmt.format(recovery.summary.latestMonthRecoveries));
  setText("recoveryShare", pct(recovery.summary.recoveriesAsPctOfActiveBase));
  setText("recoveryMonthlyShare", pct(recovery.summary.latestMonthRecoveries / current.activeGolfers));
  setText("recoveryMonthlyHeadline", fmt.format(recovery.summary.latestMonthRecoveries));
  setText("recoveryYtdHeadline", fmt.format(recovery.summary.recoveriesYTD));
  const priorRecoveryRows = membership
    .filter(row => row.year === current.year - 1 && row.reactivations != null)
    .map(row => ({ month: row.month, monthNum: row.monthNum, value: row.reactivations }));
  const currentRecoveryRows = recovery.monthlyTrend
    .map(row => ({ month: row.month, monthNum: row.monthNum, value: row.recoveries }));
  const priorCurrentMonth = priorRecoveryRows.find(row => row.monthNum === current.monthNum)?.value;
  const priorYtd = priorRecoveryRows
    .filter(row => row.monthNum <= current.monthNum)
    .reduce((total, row) => total + row.value, 0);
  const priorActiveSameMonth = membership.find(row => row.year === current.year - 1 && row.monthNum === current.monthNum)?.activeGolfers;
  const currentMonthlyShare = recovery.summary.latestMonthRecoveries / current.activeGolfers;
  const priorMonthlyShare = priorCurrentMonth / priorActiveSameMonth;
  const currentYtdShare = recovery.summary.recoveriesYTD / current.activeGolfers;
  const priorYtdShare = priorYtd / priorActiveSameMonth;
  const latestDelta = (recovery.summary.latestMonthRecoveries - priorCurrentMonth) / priorCurrentMonth;
  const ytdDelta = (recovery.summary.recoveriesYTD - priorYtd) / priorYtd;
  setText("recoveryLatestDelta", `${signedPct(latestDelta)} vs July 2025`);
  setText("recoveryYtdDelta", `${signedPct(ytdDelta)} vs Jan-July 2025`);
  setText("recoveryShareDelta", `${signedPct(currentYtdShare - priorYtdShare, 1, true)} vs July 2025`);
  setText("recoveryMonthlyShareDelta", `${signedPct(currentMonthlyShare - priorMonthlyShare, 1, true)} vs July 2025`);
  setText("recoveryMonthlyNote", `${signedPct(latestDelta)} vs July 2025.`);
  setText("recoveryYtdNote", `${signedPct(ytdDelta)} vs Jan-July 2025.`);
  renderTakeaways("page4Takeaways", [
    {
      title: "Win-back automation is the opportunity",
      body: "Recovery can become an easier source of member wins if expired-member outreach is automated and scaled nationally."
    },
    {
      title: "Retention team is testing the model",
      body: "The retention team has launched a win-back campaign to test whether this approach can work beyond a one-off effort."
    },
    {
      title: "Expired members remain reachable",
      body: "Golfers from creation years as far back as 2022 are rejoining, suggesting there is no clear statute of limitations on asking lapsed members to return."
    }
  ]);
  renderMiniBars("recoveryCreationBars", recovery.byCreationYear);
  const cumulative2025 = [];
  priorRecoveryRows.reduce((total, row) => {
    const next = total + row.value;
    cumulative2025.push({ ...row, value: next });
    return next;
  }, 0);
  const cumulative2026 = [];
  currentRecoveryRows.reduce((total, row) => {
    const next = total + row.value;
    cumulative2026.push({ ...row, value: next });
    return next;
  }, 0);
  drawRecoveryComparisonChart($("recoveryCumulativeTrend"), cumulative2025, cumulative2026, {
    max: 70000,
    tickStep: 10000,
    ticks: [0, 10000, 20000, 30000, 40000, 50000, 60000, 70000],
    callout: `2026 YTD - ${Math.round(recovery.summary.recoveriesYTD / 1000)}k`,
    endLabel2025: `${Math.round(cumulative2025.at(-1).value / 1000)}K`,
    axisFormat: value => fmt.format(value)
  });

  renderNumberList("opportunityBullets", narrative.opportunityBullets);
  renderNumberList("concernBullets", narrative.concernBullets);
  renderActions(narrative.actions);
}

function renderInterpretation(narrative, current, recovered, lost, organic) {
  const computed = [
    { title: "Current state", body: `Active membership reached ${fmt.format(current.activeGolfers)} as of ${current.month} ${current.year}, up ${fmt.format(current.netChange)} from the prior month.` },
    { title: "Primary driver", body: `${current.month} gains came from ${fmt.format(current.newGolfers)} acquired golfers and ${fmt.format(recovered)} recovered golfers, offset by ${fmt.format(lost)} losses.` },
    { title: "Leadership implication", body: `The membership base is expanding, but ${fmt.format(organic)} YTD acquisitions remain organic or untagged and require source accountability.` }
  ];
  const interpretation = computed.map((item, i) => {
    const override = narrative.interpretation?.[i];
    return override?.title || override?.body ? { title: override.title || item.title, body: override.body || item.body } : item;
  });
  $("interpretationList").innerHTML = interpretation.map(item => `<li><strong>${item.title}</strong>${item.body}</li>`).join("");
}

function renderMix(mix, total, donutId, legendId) {
  drawDonut($(donutId), mix);
  $(legendId).innerHTML = mix.map(item => `
    <div class="legend-item">
      <span class="swatch" style="background:${item.color}"></span>
      <span>${item.label}</span>
      <strong>${pct(item.value / total)}</strong>
    </div>
  `).join("");
}

function renderLegend(id, items) {
  const el = $(id);
  if (!el) return;
  el.innerHTML = items.map(item => `
    <div class="legend-item">
      <span class="swatch" style="background:${item.color}"></span>
      <span>${item.label}</span>
    </div>
  `).join("");
}

function renderSourceMixCards(id, mix, total) {
  const el = $(id);
  if (!el) return;
  el.innerHTML = mix.map(item => `
    <div class="source-mix-card">
      <span class="source-dot" style="background:${item.color}"></span>
      <div>
        <strong>${item.label}</strong>
        <em>${fmt.format(item.value)} golfers</em>
      </div>
      <b>${pct(item.value / total)}</b>
    </div>
  `).join("");
}

function sourceNote(label) {
  if (label === "GHIN Trials") return "Largest identified source.";
  if (label === "Paid Media") return "Approved paid media source.";
  return "Needs continued attribution cleanup.";
}

render().catch(error => {
  document.body.innerHTML = `<pre>${error.stack}</pre>`;
});
