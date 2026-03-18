const COLORS = {
  COMMITTED: "#1d8f6d",
  UNSAFE: "#ca4f4f",
  REJECTED: "#db8a1a",
  ABORTED: "#c26d1a",
  ERROR: "#8c3f3f",
  IN_PROGRESS: "#506d78",
  healthy: "#1d8f6d",
  degraded: "#db8a1a",
  unreachable: "#db8a1a",
  unhealthy: "#ca4f4f",
  teal: "#184b58",
  blue: "#2c6978",
  grid: "rgba(24, 75, 88, 0.12)",
};

const SERVICE_COLORS = Object.freeze({
  gateway: "#0f766e",
  safety_cluster: "#2563eb",
  sensor_gateway: "#2a9d8f",
  ot_interface: "#b45309",
  plc_adapter: "#6d597a",
  policy_store: "#7c8f2a",
  policy_admin: "#d97706",
  evidence_ledger: "#8b5e34",
  dashboard: "#475569",
});

const SERVICE_FALLBACK_PALETTE = [
  "#0f766e",
  "#2563eb",
  "#2a9d8f",
  "#b45309",
  "#6d597a",
  "#7c8f2a",
  "#8b5e34",
  "#c2410c",
  "#1d4ed8",
  "#0f766e",
];

let stream;

document.addEventListener("DOMContentLoaded", async () => {
  await fetchSnapshot();
  connectStream();
});

async function fetchSnapshot() {
  try {
    const response = await fetch("/v1/snapshot");
    const snapshot = await response.json();
    renderSnapshot(snapshot);
    setStreamState("online", "초기 스냅샷 수신");
  } catch (error) {
    setStreamState("offline", `초기 스냅샷 실패: ${error}`);
  }
}

function connectStream() {
  stream = new EventSource("/v1/stream");
  stream.addEventListener("snapshot", (event) => {
    try {
      renderSnapshot(JSON.parse(event.data));
      setStreamState("online", "실시간 연결 중");
    } catch (error) {
      setStreamState("offline", `스트림 파싱 실패: ${error}`);
    }
  });
  stream.onopen = () => setStreamState("online", "실시간 연결 중");
  stream.onerror = () => setStreamState("offline", "스트림 재연결 중");
}

function renderSnapshot(snapshot) {
  setText("last-updated", formatDateTime(snapshot.generated_at));
  renderOverview(snapshot.overview);
  renderServiceGrid(snapshot.services, snapshot.service_history);
  renderPolicySummary(snapshot.policy);
  renderAssets(snapshot.assets);
  renderTransactions(snapshot.transactions);
  renderLocks(snapshot.locks);
  renderPlc(snapshot.plc);
  renderLogs(snapshot.logs);
  renderEvaluation(snapshot.evaluation);
  renderCharts(snapshot);
}

function renderOverview(overview) {
  const cards = [
    ["활성 정책", overview.active_policy_version || "없음", `${overview.policy_version_count ?? 0}개 버전 등록`],
    ["증거 이벤트", formatInt(overview.evidence_event_count), "Evidence Ledger 누적"],
    ["트랜잭션", formatInt(overview.transaction_count), `${formatInt(overview.committed_count)} committed / ${formatInt(overview.aborted_count)} aborted`],
    ["활성 잠금", formatInt(overview.locked_count), "현재 점유 중인 자산 수"],
    ["수집 지연", formatMs(overview.collection_latency_ms), "대시보드 스냅샷 생성 시간"],
    ["대시보드 업타임", formatSeconds(overview.dashboard_uptime_s), "서비스 시작 이후"],
  ];

  document.getElementById("overview-cards").innerHTML = cards
    .map(
      ([label, value, sub]) => `
        <article class="overview-card">
          <small>${escapeHtml(label)}</small>
          <div class="overview-value">${escapeHtml(String(value ?? "-"))}</div>
          <div class="overview-sub">${escapeHtml(sub)}</div>
        </article>
      `
    )
    .join("");
}

function renderServiceGrid(services, historyMap) {
  const container = document.getElementById("service-grid");
  container.innerHTML = services
    .map((service) => {
      const history = historyMap?.[service.name] || [];
      const accent = getServiceAccent(service.name);
      const sparkline = renderSparkline(
        history.map((point) => point.latency_ms).filter((value) => value != null),
        accent.solid
      );
      const badgeClass = normalizeClass(service.status);
      const probePath = service.probe_path ? String(service.probe_path) : "";
      const serviceUrl = `${service.url || "-"}${probePath}`;
      return `
        <article class="service-card" style="--service-accent:${accent.solid}; --service-accent-soft:${accent.soft};">
          <div class="topline">
            <div class="service-heading">
              <div class="service-name">${escapeHtml(service.name)}</div>
              <div class="muted service-url">${escapeHtml(serviceUrl)}</div>
            </div>
            <span class="status-pill ${badgeClass}">${escapeHtml(service.status)}</span>
          </div>
          <div class="latency">${formatMs(service.latency_ms)}</div>
          <div class="mini-sparkline">${sparkline}</div>
          <div class="service-meta">
            <div>HTTP: ${escapeHtml(String(service.status_code ?? "-"))}</div>
            <div>오류: ${escapeHtml(service.last_error || "-")}</div>
          </div>
        </article>
      `;
    })
    .join("");
}

function renderPolicySummary(policy) {
  const container = document.getElementById("policy-summary");
  const assetCards = (policy.assets || [])
    .map(
      (asset) => `
        <article class="policy-card">
          <div class="topline">
            <div class="policy-name">${escapeHtml(asset.asset_id)}</div>
            <span class="badge good">SIL ${escapeHtml(String(asset.sil_level ?? "-"))}</span>
          </div>
          <div class="policy-meta">
            <div>Consensus: ${escapeHtml(asset.consensus_mode || "-")}</div>
            <div>Simulation: ${escapeHtml(asset.simulation_engine || "-")}</div>
            <div>Sensor: ${escapeHtml(asset.sensor_source || "-")}</div>
            <div>Executor: ${escapeHtml(asset.ot_executor || "-")}</div>
          </div>
        </article>
      `
    )
    .join("");

  container.innerHTML = `
    <div class="small-grid">
      <article class="policy-card">
        <div class="topline">
          <div class="policy-name">${escapeHtml(policy.active_policy_version || "없음")}</div>
          <span class="badge warn">${formatInt(policy.asset_count)} assets</span>
        </div>
        <div class="policy-meta">
          <div>등록 버전 수: ${formatInt(policy.policy_version_count)}</div>
          <div>자산 프로파일 수: ${formatInt(policy.asset_count)}</div>
        </div>
      </article>
      ${assetCards || '<div class="chart-empty">활성 정책 자산 정보가 없습니다.</div>'}
    </div>
  `;
}

function renderAssets(assets) {
  const container = document.getElementById("asset-grid");
  if (!assets || assets.length === 0) {
    container.innerHTML = '<div class="chart-empty">표시할 자산 스냅샷이 없습니다.</div>';
    return;
  }

  container.innerHTML = assets
    .map(
      (asset) => `
        <article class="asset-card">
          <div class="topline">
            <div class="asset-name">${escapeHtml(asset.asset_id)}</div>
            <span class="status-pill ${normalizeClass(asset.status)}">${escapeHtml(asset.status)}</span>
          </div>
          <div class="asset-meta">
            <div>소스 힌트: ${escapeHtml(asset.source_hint || "-")}</div>
            <div>지연: ${formatMs(asset.latency_ms)}</div>
            <div>신뢰도: ${asset.sensor_reliability_index != null ? Number(asset.sensor_reliability_index).toFixed(2) : "-"}</div>
            <div>해시: ${escapeHtml(shortHash(asset.sensor_snapshot_hash))}</div>
            ${asset.error ? `<div>오류: ${escapeHtml(asset.error)}</div>` : ""}
          </div>
          <div class="field-list">
            ${(asset.summary_fields || [])
              .map(
                (field) => {
                  const valueText = formatAssetFieldValue(field.value);
                  return `
                  <div class="field-row">
                    <span class="label">${escapeHtml(field.name)}</span>
                    <strong class="field-value" title="${escapeHtml(String(field.value ?? "-"))}">${escapeHtml(valueText)}</strong>
                  </div>
                `;
                }
              )
              .join("")}
          </div>
        </article>
      `
    )
    .join("");
}

function renderTransactions(transactions) {
  const tbody = document.getElementById("transaction-table");
  if (!transactions || transactions.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8">최근 트랜잭션이 없습니다.</td></tr>';
    return;
  }

  tbody.innerHTML = transactions
    .map(
      (item) => `
        <tr>
          <td>
            <strong>${escapeHtml(item.transaction_id)}</strong>
            ${item.reason_excerpt ? `<div class="muted">${escapeHtml(item.reason_excerpt)}</div>` : ""}
          </td>
          <td>${escapeHtml(item.asset_id || "-")}</td>
          <td><span class="status-pill ${normalizeClass(item.final_status)}">${escapeHtml(item.final_status)}</span></td>
          <td>${escapeHtml(item.latest_stage || "-")}</td>
          <td>${formatInt(item.event_count)}</td>
          <td>${formatMs(item.duration_ms)}</td>
          <td>${escapeHtml(formatDateTime(item.latest_created_at))}</td>
          <td>${item.evidence_url ? `<a class="link" href="${escapeHtml(item.evidence_url)}" target="_blank" rel="noreferrer">Evidence</a>` : "-"}</td>
        </tr>
      `
    )
    .join("");
}

function renderLocks(locks) {
  const container = document.getElementById("lock-list");
  if (!locks || locks.length === 0) {
    container.innerHTML = '<div class="chart-empty">현재 활성 잠금이 없습니다.</div>';
    return;
  }
  container.innerHTML = `<div class="lock-list">${locks
    .map(
      (lock) => `
        <div class="lock-row">
          <div>
            <strong>${escapeHtml(lock.asset_id)}</strong>
            <div class="muted">${escapeHtml(lock.transaction_id)}</div>
          </div>
          <div>
            <strong>${formatMs(lock.remaining_ms)}</strong>
            <div class="muted">남은 TTL</div>
          </div>
        </div>
      `
    )
    .join("")}</div>`;
}

function renderPlc(plc) {
  const container = document.getElementById("plc-summary");
  const connections = plc?.connections || [];
  container.innerHTML = `
    <div class="small-grid">
      <article class="plc-card">
        <div class="topline">
          <div class="policy-name">PLC Adapter</div>
          <span class="status-pill ${normalizeClass(plc?.status || "unknown")}">${escapeHtml(plc?.status || "unknown")}</span>
        </div>
        <div class="policy-meta">
          <div>응답 지연: ${formatMs(plc?.latency_ms)}</div>
          <div>연결 수: ${formatInt(connections.length)}</div>
          <div>상태 코드: ${escapeHtml(String(plc?.status_code ?? "-"))}</div>
          ${plc?.error ? `<div>오류: ${escapeHtml(plc.error)}</div>` : ""}
        </div>
      </article>
      ${connections
        .map(
          (connection) => `
            <article class="plc-card">
              <div class="topline">
                <div class="policy-name">${escapeHtml(connection.connection_key)}</div>
                <span class="status-pill ${normalizeClass(connection.connected ? "healthy" : "unhealthy")}">${
                  connection.connected ? "connected" : "disconnected"
                }</span>
              </div>
              <div class="policy-meta">
                <div>last_error: ${escapeHtml(connection.last_error || "-")}</div>
              </div>
            </article>
          `
        )
        .join("")}
    </div>
  `;
}

function renderLogs(logs) {
  const container = document.getElementById("log-list");
  if (!logs || logs.length === 0) {
    container.innerHTML = '<div class="chart-empty">표시할 로그가 없습니다.</div>';
    return;
  }

  container.innerHTML = logs
    .map(
      (log) => `
        <div class="log-row">
          <div class="log-head">
            <span class="status-pill ${normalizeClass(levelToStatus(log.level))}">${escapeHtml(log.level || "INFO")}</span>
            <strong>${escapeHtml(log.service || "unknown")}</strong>
            <span class="muted">${escapeHtml(log.timestamp || "-")}</span>
            ${log.tx ? `<span class="muted">tx=${escapeHtml(log.tx)}</span>` : ""}
            ${log.asset ? `<span class="muted">asset=${escapeHtml(log.asset)}</span>` : ""}
            ${log.mod ? `<span class="muted">${escapeHtml(log.mod)}</span>` : ""}
          </div>
          <div class="log-message">${escapeHtml(log.message || "")}</div>
        </div>
      `
    )
    .join("");
}

function renderEvaluation(evaluation) {
  const container = document.getElementById("evaluation-summary");
  const single = evaluation?.single;
  const repeat = evaluation?.repeat;
  const flaky = repeat?.flaky_cases || [];

  container.innerHTML = `
    <div class="small-grid">
      <article class="evaluation-card">
        <div class="topline">
          <div class="policy-name">단일 Live 평가</div>
          <span class="badge good">${single?.accuracy_pct != null ? `${single.accuracy_pct.toFixed(2)}%` : "-"}</span>
        </div>
        <div class="policy-meta">
          <div>passed / total: ${formatInt(single?.passed)} / ${formatInt(single?.total)}</div>
          <div>failed: ${formatInt(single?.failed)}</div>
          <div>생성 시각: ${escapeHtml(formatTimeMs(single?.generated_at_ms))}</div>
          ${single?.error ? `<div>오류: ${escapeHtml(single.error)}</div>` : ""}
        </div>
      </article>
      <article class="evaluation-card">
        <div class="topline">
          <div class="policy-name">반복 Live 평가</div>
          <span class="badge ${repeat?.loss_rate_pct > 0 ? "warn" : "good"}">${
            repeat?.overall_accuracy_pct != null ? `${Number(repeat.overall_accuracy_pct).toFixed(2)}%` : "-"
          }</span>
        </div>
        <div class="policy-meta">
          <div>runs: ${formatInt(repeat?.runs)}</div>
          <div>loss rate: ${repeat?.loss_rate_pct != null ? `${Number(repeat.loss_rate_pct).toFixed(2)}%` : "-"}</div>
          <div>run success: ${repeat?.run_success_rate_pct != null ? `${Number(repeat.run_success_rate_pct).toFixed(2)}%` : "-"}</div>
          <div>생성 시각: ${escapeHtml(formatTimeMs(repeat?.generated_at_ms))}</div>
          ${repeat?.error ? `<div>오류: ${escapeHtml(repeat.error)}</div>` : ""}
        </div>
      </article>
    </div>
    <div class="subsection">
      <h3>Flaky Case</h3>
      ${
        flaky.length
          ? `<div class="metric-list">${flaky
              .map(
                (item) => `
                  <div class="metric-row">
                    <span class="label">${escapeHtml(item.case_id)}</span>
                    <strong>${Number(item.pass_rate_pct).toFixed(2)}% pass</strong>
                  </div>
                `
              )
              .join("")}</div>`
          : '<div class="chart-empty">최근 반복 평가에서 flaky case가 없습니다.</div>'
      }
    </div>
  `;
}

function renderCharts(snapshot) {
  renderServiceLatencyChart(snapshot.services, snapshot.service_history);
  renderOutcomeTimeseries(snapshot.pipeline?.outcome_timeseries || []);
  renderFinalStatusDonut(snapshot.pipeline?.latest_outcome_counts || {});
  renderConsensusChart(snapshot.safety?.consensus_score_series || []);
  renderUnsafeReasonBars(snapshot.safety?.unsafe_reason_counts || []);
}

function renderServiceLatencyChart(services, historyMap) {
  const visible = services
    .map((service) => ({
      label: service.name,
      color: getServiceColor(service.name),
      points: (historyMap?.[service.name] || []).filter((point) => point.latency_ms != null),
    }))
    .filter((series) => series.points.length > 1)
    .slice(0, 8);

  const host = document.getElementById("service-latency-chart");
  host.innerHTML = buildLineChart(visible, {
    yAccessor: (point) => point.latency_ms,
    height: 250,
    unit: "ms",
  });
}

function renderOutcomeTimeseries(buckets) {
  const host = document.getElementById("outcome-timeseries-chart");
  host.innerHTML = buildStackedBarChart(buckets, ["COMMITTED", "UNSAFE", "REJECTED", "ABORTED", "ERROR", "IN_PROGRESS"]);
}

function renderFinalStatusDonut(counts) {
  const host = document.getElementById("final-status-chart");
  host.innerHTML = buildDonutChart(counts);
}

function renderConsensusChart(points) {
  const host = document.getElementById("consensus-score-chart");
  const series = [{ label: "score", color: COLORS.blue, points }];
  host.innerHTML = buildLineChart(series, {
    yAccessor: (point) => point.score,
    height: 250,
    maxValue: 1,
    unit: "",
  });
}

function renderUnsafeReasonBars(items) {
  const host = document.getElementById("unsafe-reasons-chart");
  if (!items || items.length === 0) {
    host.innerHTML = '<div class="chart-empty">최근 UNSAFE 이벤트가 없습니다.</div>';
    return;
  }
  const maxValue = Math.max(...items.map((item) => item.count), 1);
  host.innerHTML = `
    <div class="bar-list">
      ${items
        .map(
          (item) => `
            <div class="bar-item">
              <div class="metric-row">
                <span class="label">${escapeHtml(item.label)}</span>
                <strong>${formatInt(item.count)}</strong>
              </div>
              <div class="bar-track">
                <div class="bar-fill" style="width:${(item.count / maxValue) * 100}%; background:${COLORS.REJECTED};"></div>
              </div>
            </div>
          `
        )
        .join("")}
    </div>
  `;
}

function buildLineChart(seriesList, options) {
  if (!seriesList || seriesList.length === 0) {
    return '<div class="chart-empty">표시할 시계열 데이터가 없습니다.</div>';
  }

  const width = 760;
  const height = options.height || 220;
  const pad = { top: 18, right: 18, bottom: 28, left: 40 };
  const plotWidth = width - pad.left - pad.right;
  const plotHeight = height - pad.top - pad.bottom;
  const values = seriesList.flatMap((series) => series.points.map((point) => Number(options.yAccessor(point) ?? 0)));
  const maxValue = options.maxValue ?? Math.max(...values, 1);
  const pointCount = Math.max(...seriesList.map((series) => series.points.length), 1);

  const grid = Array.from({ length: 4 }, (_, index) => {
    const ratio = index / 3;
    const y = pad.top + plotHeight * ratio;
    const label = ((1 - ratio) * maxValue).toFixed(options.maxValue === 1 ? 2 : 0);
    return `
      <line x1="${pad.left}" y1="${y}" x2="${width - pad.right}" y2="${y}" stroke="${COLORS.grid}" stroke-width="1"/>
      <text x="${pad.left - 10}" y="${y + 4}" text-anchor="end" fill="#5d747d" font-size="11">${label}${options.unit || ""}</text>
    `;
  }).join("");

  const paths = seriesList
    .map((series) => {
      const points = series.points
        .map((point, index) => {
          const x = pad.left + (pointCount === 1 ? plotWidth / 2 : (index / (pointCount - 1)) * plotWidth);
          const yValue = Number(options.yAccessor(point) ?? 0);
          const y = pad.top + plotHeight - (yValue / maxValue) * plotHeight;
          return `${x},${y}`;
        })
        .join(" ");
      return `<polyline fill="none" stroke="${series.color}" stroke-width="3" stroke-linejoin="round" stroke-linecap="round" points="${points}"/>`;
    })
    .join("");

  const labels = buildXAxisLabels(seriesList[0].points, width, height, pad);
  const legend = buildLegend(seriesList.map((series) => ({ label: series.label, color: series.color })));

  return `
    <svg viewBox="0 0 ${width} ${height}" width="100%" height="${height}" aria-hidden="true">
      ${grid}
      ${paths}
      ${labels}
    </svg>
    ${legend}
  `;
}

function buildStackedBarChart(buckets, keys) {
  if (!buckets || buckets.length === 0) {
    return '<div class="chart-empty">표시할 분 단위 집계가 없습니다.</div>';
  }

  const width = 760;
  const height = 250;
  const pad = { top: 18, right: 18, bottom: 28, left: 34 };
  const plotWidth = width - pad.left - pad.right;
  const plotHeight = height - pad.top - pad.bottom;
  const maxValue = Math.max(...buckets.map((bucket) => keys.reduce((sum, key) => sum + Number(bucket[key] || 0), 0)), 1);
  const barWidth = plotWidth / Math.max(buckets.length, 1);

  const bars = buckets
    .map((bucket, index) => {
      let currentY = pad.top + plotHeight;
      const x = pad.left + index * barWidth + 5;
      const widthInner = Math.max(barWidth - 8, 8);
      const segments = keys
        .map((key) => {
          const value = Number(bucket[key] || 0);
          if (!value) {
            return "";
          }
          const segmentHeight = (value / maxValue) * plotHeight;
          currentY -= segmentHeight;
          return `<rect x="${x}" y="${currentY}" width="${widthInner}" height="${segmentHeight}" rx="4" fill="${COLORS[key]}"/>`;
        })
        .join("");

      return `${segments}<text x="${x + widthInner / 2}" y="${height - 8}" text-anchor="middle" fill="#5d747d" font-size="11">${bucket.label}</text>`;
    })
    .join("");

  return `
    <svg viewBox="0 0 ${width} ${height}" width="100%" height="${height}" aria-hidden="true">
      ${bars}
    </svg>
    ${buildLegend(keys.map((key) => ({ label: key, color: COLORS[key] })))}
  `;
}

function buildDonutChart(counts) {
  const entries = Object.entries(counts || {}).filter(([, value]) => value > 0);
  if (entries.length === 0) {
    return '<div class="chart-empty">표시할 최종 상태 데이터가 없습니다.</div>';
  }

  const total = entries.reduce((sum, [, value]) => sum + value, 0);
  const radius = 76;
  const circumference = 2 * Math.PI * radius;
  let offset = 0;

  const segments = entries
    .map(([label, value]) => {
      const dash = (value / total) * circumference;
      const segment = `
        <circle
          cx="110"
          cy="110"
          r="${radius}"
          fill="none"
          stroke="${COLORS[label]}"
          stroke-width="24"
          stroke-dasharray="${dash} ${circumference - dash}"
          stroke-dashoffset="${-offset}"
          transform="rotate(-90 110 110)"
        />`;
      offset += dash;
      return segment;
    })
    .join("");

  return `
    <div style="display:grid; place-items:center;">
      <svg viewBox="0 0 220 220" width="240" height="240" aria-hidden="true">
        <circle cx="110" cy="110" r="${radius}" fill="none" stroke="rgba(24,75,88,0.08)" stroke-width="24"/>
        ${segments}
        <text x="110" y="104" text-anchor="middle" font-size="15" fill="#5d747d">최근 상태</text>
        <text x="110" y="132" text-anchor="middle" font-size="30" font-weight="800" fill="#184b58">${total}</text>
      </svg>
    </div>
    ${buildLegend(entries.map(([label]) => ({ label, color: COLORS[label] })))}
  `;
}

function buildLegend(items) {
  return `
    <div class="legend">
      ${items
        .map(
          (item) => `
            <span class="legend-item">
              <span class="legend-swatch" style="background:${item.color};"></span>
              ${escapeHtml(item.label)}
            </span>
          `
        )
        .join("")}
    </div>
  `;
}

function buildXAxisLabels(points, width, height, pad) {
  if (!points || points.length === 0) {
    return "";
  }
  const pointCount = points.length;
  const plotWidth = width - pad.left - pad.right;
  const indexes = Array.from(new Set([0, Math.floor((pointCount - 1) / 2), pointCount - 1]));
  return indexes
    .map((index) => {
      const point = points[index];
      const x = pad.left + (pointCount === 1 ? plotWidth / 2 : (index / (pointCount - 1)) * plotWidth);
      return `<text x="${x}" y="${height - 6}" text-anchor="middle" fill="#5d747d" font-size="11">${escapeHtml(point.label || "")}</text>`;
    })
    .join("");
}

function renderSparkline(values, color) {
  if (!values || values.length < 2) {
    return '<div class="chart-empty">데이터 없음</div>';
  }
  const width = 220;
  const height = 56;
  const maxValue = Math.max(...values, 1);
  const points = values
    .map((value, index) => {
      const x = (index / (values.length - 1)) * (width - 8) + 4;
      const y = height - (value / maxValue) * (height - 8) - 4;
      return `${x},${y}`;
    })
    .join(" ");
  return `
    <svg viewBox="0 0 ${width} ${height}" width="100%" height="${height}" aria-hidden="true">
      <polyline fill="none" stroke="${color}" stroke-width="3" stroke-linecap="round" points="${points}"/>
    </svg>
  `;
}

function setStreamState(kind, text) {
  const el = document.getElementById("stream-status");
  el.className = `stream-pill ${kind}`;
  el.textContent = text;
}

function setText(id, text) {
  const el = document.getElementById(id);
  if (el) {
    el.textContent = text;
  }
}

function normalizeClass(value) {
  return String(value || "unknown").toLowerCase().replace(/\s+/g, "_");
}

function normalizeServiceName(name) {
  return String(name || "")
    .trim()
    .toLowerCase()
    .replace(/[^\w]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

function hashString(value) {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash << 5) - hash + value.charCodeAt(index);
    hash |= 0;
  }
  return Math.abs(hash);
}

function hexToRgba(hex, alpha) {
  const normalized = hex.replace("#", "");
  const source = normalized.length === 3
    ? normalized.split("").map((char) => char + char).join("")
    : normalized;
  const red = Number.parseInt(source.slice(0, 2), 16);
  const green = Number.parseInt(source.slice(2, 4), 16);
  const blue = Number.parseInt(source.slice(4, 6), 16);
  return `rgba(${red}, ${green}, ${blue}, ${alpha})`;
}

function getServiceColor(name) {
  const normalized = normalizeServiceName(name);
  if (SERVICE_COLORS[normalized]) {
    return SERVICE_COLORS[normalized];
  }
  return SERVICE_FALLBACK_PALETTE[hashString(normalized) % SERVICE_FALLBACK_PALETTE.length];
}

function getServiceAccent(name) {
  const solid = getServiceColor(name);
  return {
    solid,
    soft: hexToRgba(solid, 0.12),
  };
}

function levelToStatus(level) {
  const upper = String(level || "").toUpperCase();
  if (upper === "INFO") return "healthy";
  if (upper === "DEBUG") return "in_progress";
  if (upper === "WARNING") return "degraded";
  return "unhealthy";
}

function shortHash(hash) {
  if (!hash) return "-";
  return `${hash.slice(0, 10)}...${hash.slice(-6)}`;
}

function formatAssetFieldValue(value) {
  if (value == null) return "-";
  const text = String(value).replace(/\s+/g, " ").trim();
  if (!text) return "-";
  if (text.length <= 44) return text;
  if (text.startsWith("[") && text.endsWith("]")) {
    return `${text.slice(0, 30)} ... ${text.slice(-10)}`;
  }
  return `${text.slice(0, 38)}...`;
}

function formatMs(value) {
  if (value == null || Number.isNaN(Number(value))) return "-";
  const numeric = Number(value);
  if (numeric >= 1000) return `${(numeric / 1000).toFixed(2)} s`;
  return `${numeric.toFixed(1)} ms`;
}

function formatSeconds(value) {
  if (value == null || Number.isNaN(Number(value))) return "-";
  const numeric = Number(value);
  if (numeric >= 3600) return `${(numeric / 3600).toFixed(1)} h`;
  if (numeric >= 60) return `${(numeric / 60).toFixed(1)} min`;
  return `${numeric.toFixed(1)} s`;
}

function formatInt(value) {
  if (value == null || Number.isNaN(Number(value))) return "-";
  return Number(value).toLocaleString("ko-KR");
}

function formatDateTime(value) {
  if (!value) return "-";
  try {
    return new Date(value).toLocaleString("ko-KR", { hour12: false });
  } catch {
    return String(value);
  }
}

function formatTimeMs(value) {
  if (!value) return "-";
  return new Date(Number(value)).toLocaleString("ko-KR", { hour12: false });
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
