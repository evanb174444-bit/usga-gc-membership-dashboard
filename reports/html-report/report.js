const fmt = new Intl.NumberFormat("en-US");
const pct = (v, digits = 1) => `${(v * 100).toFixed(digits)}%`;

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

const defaultNarrative = {
  eyebrow: "GC Membership",
  reportMonth: "August 2026",
  reportDate: "Report Date: August 2, 2026",
  page1Title: "Executive Membership Report",
  page1Dek: "Topline membership position, acquisition mix, and operating implications for leadership review.",
  activeKpiLabel: "Total Active Membership",
  netKpiLabel: "Net Membership Change",
  ytdKpiLabel: "Year-to-Date Growth",
  annualKpiLabel: "Twelve-Month Change",
  trendLabel: "Membership Trend",
  trendTitle: "Total Active Members",
  trendNote: "Rolling view of active membership through the latest completed report month.",
  interpretationLabel: "Interpretation",
  interpretationTitle: "What leadership should know",
  movementLabel: "Membership Movement",
  movementTitle: "July Operating Bridge",
  movementNote: "Opening membership plus acquired and recovered golfers, net of losses, reconciles to closing active membership.",
  mixLabel: "Acquisition Mix",
  mixTitle: "Where New Members Came From",
  retentionLabel: "Retention + Recovery",
  retentionTitle: "Preserving Membership",
  renewalMiniLabel: "Renewal Rate",
  recoveredMiniLabel: "Recovered",
  retentionReadoutLabel: "Operating readout",
  footerLeft: "GC Membership Executive Report",

  page2Eyebrow: "Acquisition + Segmentation",
  page2Title: "How Membership Is Growing",
  page2Dek: "A focused view of gross additions, attribution momentum, and the source mix contributing most to current growth.",
  newMembersLabel: "New Members",
  trialsLabel: "GHIN Trial Conversions",
  paidLabel: "Paid Media Conversions",
  acqTrendLabel: "Acquisition Trend",
  acqTrendTitle: "Monthly New Members",
  acqMixPageLabel: "Source Mix",
  acqMixPageTitle: "YTD Acquisition Mix",
  segmentLabel: "Segment Performance",
  segmentTitle: "Executive Source Readout",
  page2NotesLabel: "Executive Takeaway",

  page3Eyebrow: "Retention + Recovery",
  page3Title: "How Membership Is Being Preserved",
  page3Dek: "Retention and recovery indicators showing how effectively the member base is being protected.",
  renewalPageLabel: "Renewal Rate",
  retainedPageLabel: "Members Retained",
  recoveryPageLabel: "Recovered Members",
  retentionTrendLabel: "Retention Trend",
  retentionTrendTitle: "On-Time Renewal Rate",
  recoveryTrendLabel: "Recovery Trend",
  recoveryTrendTitle: "Monthly Recoveries",
  cohortLabel: "Cohort View",
  cohortTitle: "Retention by Member Tenure",
  page3NotesLabel: "Executive Takeaway",

  page4Eyebrow: "Engagement",
  page4Title: "GHIN Challenges Momentum",
  page4Dek: "Engagement indicators showing program scale, participating associations, and golfer activity.",
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
  page4NotesLabel: "Executive Takeaway",

  page5Eyebrow: "Leadership Agenda",
  page5Title: "Opportunities, Concerns & Actions",
  page5Dek: "A final page that turns dashboard movement into clear priorities, risks, and decisions for leadership.",
  opportunitiesLabel: "Opportunities",
  opportunitiesTitle: "Where momentum can be extended",
  concernsLabel: "Concerns",
  concernsTitle: "Where leadership attention is needed",
  actionsLabel: "Recommended Actions",
  actionsTitle: "Near-Term Decisions and Follow-Ups",
  decisionLabel: "Leadership Decision Required",
  decisionText: "Confirm which source categories and workstream decisions should be elevated into the monthly executive report archive.",

  interpretation: [null, null, null],
  page2Bullets: [
    "GHIN Trials remain the largest identified acquisition source and should be monitored as a conversion engine.",
    "Paid Media is material but currently only covers the approved paid media attribution source.",
    "Organic / Unknown remains large enough to require continued attribution cleanup."
  ],
  page3Bullets: [
    "Retention remains a meaningful counterweight to acquisition and should stay visible in the executive readout.",
    "Recovery adds incremental lift to the active base and should reconcile to the dashboard recovery source.",
    "Cohort health remains strongest in newer member years and should be watched as cohorts mature."
  ],
  page4Bullets: [
    "GHIN Challenges show strong program growth from the first available snapshot to the latest snapshot.",
    "Participation and ranked golfer rates provide a clearer engagement read than challenge counts alone.",
    "Top AGA performance can help identify repeatable engagement patterns."
  ],
  opportunityBullets: [
    "Trial conversion engine generated the largest identified acquisition contribution.",
    "Membership momentum remains positive through the latest completed report month.",
    "Engagement expansion creates a broader activation story beyond acquisition."
  ],
  concernBullets: [
    "Organic / Unknown acquisition remains large and limits source accountability.",
    "Paid Media timing and coverage must be kept explicit in the executive report.",
    "Manual workstream commentary still requires owner validation before publication."
  ],
  actions: [
    { priority: "1", action: "Validate source attribution categories for the monthly executive report.", owner: "Analytics", timing: "Before final PDF" },
    { priority: "2", action: "Confirm narrative commentary and leadership implications.", owner: "Leadership", timing: "Monthly review" },
    { priority: "3", action: "Archive approved PDF and HTML snapshot for the report month.", owner: "Reporting", timing: "After approval" }
  ]
};

async function loadNarrative() {
  try {
    const key = new URLSearchParams(location.search).get("report") || "current";
    const archived = await loadArchivedCopy(key);
    const raw = localStorage.getItem(`gcExecutiveReportNarrative:${key}`) || localStorage.getItem("gcExecutiveReportNarrative");
    const draft = raw ? JSON.parse(raw) : {};
    return deepMerge(deepMerge(defaultNarrative, archived), draft);
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

function drawDonut(svg, items) {
  if (!svg) return;
  const cx = 110, cy = 110, r = 78, stroke = 34;
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
  svg.innerHTML = `${arcs}<circle cx="${cx}" cy="${cy}" r="48" fill="#fff"/><text x="${cx}" y="${cy - 5}" text-anchor="middle" fill="${colors.navy}" font-size="11">YTD</text><text x="${cx}" y="${cy + 12}" text-anchor="middle" fill="${colors.navy}" font-size="11">ACQUISITION</text>`;
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

function renderNumberList(id, items) {
  const el = $(id);
  if (!el) return;
  el.innerHTML = items.map((item, i) => `<li><span>${String(i + 1).padStart(2, "0")}</span><p>${item}</p></li>`).join("");
}

function renderActions(items) {
  $("actionsTable").innerHTML = items.map(row => `<tr><td>${row.priority}</td><td>${row.action}</td><td>${row.owner}</td><td>${row.timing}</td></tr>`).join("");
}

async function render() {
  const narrative = await loadNarrative();
  const [membership, ghin, marketing, recovery, cohorts, challenges, challengeGrowth] = await Promise.all([
    loadJson("../../data/membership_monthly.json"),
    loadJson("../../data/ghin_trials.json"),
    loadJson("../../data/marketing_analysis.json"),
    loadJson("../../data/recovery_analysis.json"),
    loadJson("../../data/retention_cohorts.json"),
    loadJson("../../data/processed/ghin_challenges.json"),
    loadJson("../../data/processed/ghin_challenges_growth.json")
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
  const trials = ghin.summary.trialConversions;
  const organic = ytdNew - trials - paidMedia;
  const mix = [
    { label: "GHIN Trials", value: trials, color: colors.navy },
    { label: "Paid Media", value: paidMedia, color: colors.lightBlue },
    { label: "Organic / Unknown", value: organic, color: colors.paleBlue }
  ];

  setText("activeMembers", fmt.format(current.activeGolfers));
  setText("activeSub", `${pct(current.percentChange)} vs prior month`);
  setText("netChange", `+${fmt.format(current.netChange)}`);
  setText("netSub", `${current.month} net active members`);
  setText("ytdGrowth", `+${fmt.format(ytdGrowth)}`);
  setText("ytdSub", `+${pct(ytdGrowth / dec.activeGolfers)} vs December`);
  setText("annualChange", `+${pct(annualGrowth)}`);
  setText("annualSub", `vs ${priorYear.month} ${priorYear.year}`);
  setText("renewalRate", pct(current.onTimeRenewalRate));
  setText("recoveredMembers", fmt.format(recovered));
  setText("retentionReadout", `${fmt.format(current.renewed)} golfers renewed on time in ${current.month}, while ${fmt.format(recovery.summary.recoveriesYTD)} recovered members have returned year to date.`);

  const trendRows = membership.filter(row => row.year === current.year && row.monthNum <= current.monthNum && row.activeGolfers != null);
  drawLineChart($("membershipTrend"), trendRows.map(row => row.activeGolfers), trendRows.map(row => row.month.slice(0, 1)));
  renderBridge({ opening: prior.activeGolfers, acquired: current.newGolfers, lost, recovered, closing: current.activeGolfers });
  renderInterpretation(narrative, current, recovered, lost, organic);
  renderMix(mix, ytdNew, "mixDonut", "mixLegend");
  renderMix(mix, ytdNew, "mixDonutPage2", "mixLegendPage2");

  setText("newMembers", fmt.format(current.newGolfers));
  setText("newMembersSub", `${current.month} gross additions`);
  setText("trialConversions", fmt.format(trials));
  setText("paidConversions", fmt.format(paidMedia));
  drawBarChart($("acquisitionBars"), ytdRows.map(row => row.newGolfers), ytdRows.map(row => row.month.slice(0, 3)));
  $("sourceTable").innerHTML = mix.map(item => `<tr><td>${item.label}</td><td>${fmt.format(item.value)}</td><td>${pct(item.value / ytdNew)}</td><td>${sourceNote(item.label)}</td></tr>`).join("");
  renderList("page2Bullets", narrative.page2Bullets);

  setText("renewalRatePage", pct(current.onTimeRenewalRate));
  setText("membersRetained", fmt.format(current.renewed));
  setText("recoveryPageMembers", fmt.format(recovered));
  drawLineChart($("retentionTrend"), ytdRows.map(row => row.onTimeRenewalRate || 0), ytdRows.map(row => row.month.slice(0, 3)), { color: colors.teal });
  drawBarChart($("recoveryTrend"), recovery.monthlyTrend.map(row => row.recoveries), recovery.monthlyTrend.map(row => row.month.slice(0, 3)), { color: colors.green });
  $("cohortTable").innerHTML = cohorts.summary.slice(3, 6).map(row => `<tr><td>${row.label}</td><td>${row.valueDisplay}</td><td>${row.subDisplay}</td></tr>`).join("");
  renderList("page3Bullets", narrative.page3Bullets);

  const c = challenges.summary;
  setText("totalChallenges", fmt.format(c.totalChallenges));
  setText("challengeGolfers", fmt.format(c.totalGolfers));
  setText("rankedGolfers", fmt.format(c.rankedGolfers));
  setText("scoresPosted", fmt.format(c.scoresPosted));
  setText("rankedRate", pct(c.rankedGolferRate));
  setText("scoresPerGolfer", c.scoresPerGolfer.toFixed(1));
  setText("participatingAgas", fmt.format(challengeGrowth.at(-1).participatingAssociations));
  drawLineChart($("challengeGrowth"), challengeGrowth.map(row => row.totalGolfers), challengeGrowth.map(row => row.label), { color: colors.green, zero: true });
  $("agaTable").innerHTML = challenges.topAgasByGolfers.slice(0, 6).map(row => `<tr><td>${row.aga}</td><td>${fmt.format(row.totalChallenges)}</td><td>${fmt.format(row.totalGolfers)}</td><td>${pct(row.rankedGolferRate)}</td></tr>`).join("");
  renderList("page4Bullets", narrative.page4Bullets);

  renderNumberList("opportunityBullets", narrative.opportunityBullets);
  renderNumberList("concernBullets", narrative.concernBullets);
  renderActions(narrative.actions);
}

function renderInterpretation(narrative, current, recovered, lost, organic) {
  const computed = [
    { title: "Current state", body: `Active membership reached ${fmt.format(current.activeGolfers)} as of ${current.month} ${current.year}, up ${fmt.format(current.netChange)} from the prior month.` },
    { title: "Primary driver", body: `${current.month} gains came from ${fmt.format(current.newGolfers)} acquired golfers and ${fmt.format(recovered)} recovered golfers, offset by ${fmt.format(lost)} losses.` },
    { title: "Leadership implication", body: `The membership base is expanding, but ${fmt.format(organic)} YTD acquisitions remain organic or unknown and require source accountability.` }
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

function sourceNote(label) {
  if (label === "GHIN Trials") return "Largest identified source.";
  if (label === "Paid Media") return "Approved paid media source.";
  return "Needs continued attribution cleanup.";
}

render().catch(error => {
  document.body.innerHTML = `<pre>${error.stack}</pre>`;
});
