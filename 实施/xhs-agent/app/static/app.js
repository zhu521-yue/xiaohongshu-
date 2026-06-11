const state = {
  currentRunId: null,
  currentRun: null,
  pollTimer: null,
};

const $ = (selector) => document.querySelector(selector);

const elements = {
  serviceStatus: $("#serviceStatus"),
  queueStrip: $("#queueStrip"),
  queueDetail: $("#queueDetail"),
  runForm: $("#runForm"),
  submitButton: $("#submitButton"),
  formNotice: $("#formNotice"),
  refreshButton: $("#refreshButton"),
  runList: $("#runList"),
  currentStatus: $("#currentStatus"),
  summaryGrid: $("#summaryGrid"),
  runDiagnostics: $("#runDiagnostics"),
  reviewActions: $("#reviewActions"),
  approveRunButton: $("#approveRunButton"),
  rejectRunButton: $("#rejectRunButton"),
  creatorAssetInput: $("#creatorAssetInput"),
  attachCreatorAssetsButton: $("#attachCreatorAssetsButton"),
  creatorPublishCheckbox: $("#creatorPublishCheckbox"),
  reviewNotice: $("#reviewNotice"),
  draftTab: $("#draftTab"),
  insightsTab: $("#insightsTab"),
  rawTab: $("#rawTab"),
  performanceForm: $("#performanceForm"),
  performanceNotice: $("#performanceNotice"),
  syncCreatorNotesButton: $("#syncCreatorNotesButton"),
  creatorNotesList: $("#creatorNotesList"),
  memoryList: $("#memoryList"),
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function apiGet(path) {
  const response = await fetch(path);
  const data = await response.json();
  if (!response.ok || data.ok === false) {
    throw new Error(data.error || `GET ${path} failed`);
  }
  return data;
}

async function apiPost(path, payload) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok || data.ok === false) {
    throw new Error(data.error || `POST ${path} failed`);
  }
  return data;
}

function statusClass(status) {
  if (status === "success") return "status-success";
  if (status === "failed") return "status-failed";
  if (status === "running" || status === "queued") return "status-running";
  return "";
}

function setNotice(element, message, isError = false) {
  element.textContent = message || "";
  element.classList.toggle("error", Boolean(isError));
}

function metric(label, value) {
  return `<div class="metric"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value ?? "-")}</strong></div>`;
}

function creatorPublishStatusLabel(status) {
  if (status === "success") return "成功";
  if (status === "failed") return "失败";
  return "未请求";
}

function creatorPublishError(summary) {
  return summary.creator_publish_error || "";
}

function performanceStatusLabel(status) {
  if (status === "performance_recorded") return "已录入";
  if (status === "published") return "待录入";
  if (status === "draft_saved") return "待录入";
  if (status === "draft_pending") return "待保存";
  return status || "-";
}

function performanceDataSummary(performanceData) {
  const data = performanceData || {};
  return [
    `曝光 ${data.views ?? 0}`,
    `赞 ${data.likes ?? 0}`,
    `藏 ${data.collects ?? 0}`,
    `评 ${data.comments ?? 0}`,
    `关 ${data.follows ?? 0}`,
  ].join(" / ");
}

function memoryMetaGrid(record) {
  return `
    <div class="memory-meta-grid">
      ${metric("创作发布", creatorPublishStatusLabel(record.creator_publish_status))}
      ${metric("平台笔记", record.creator_note_id)}
      ${metric("表现状态", performanceStatusLabel(record.status))}
      ${metric("表现分", record.performance_score ?? 0)}
    </div>
    <p class="muted">${escapeHtml(performanceDataSummary(record.performance_data))}</p>
  `;
}

function fillPerformanceFromMemoryRecord(record) {
  elements.performanceForm.elements.post_id.value = record.postId || "";
  elements.performanceForm.elements.creator_note_id.value = record.creatorNoteId || "";
  setNotice(elements.performanceNotice, `已选择运营记忆：${record.recordId || "-"}`);
}

function diagnoseRunFailure(run) {
  if (run?.failure_category_label) return run.failure_category_label;
  if (run?.summary?.failure_category_label) return run.summary.failure_category_label;

  const text = [
    run?.error,
    run?.summary?.creator_publish_error,
    run?.state?.error,
    run?.state?.creator_publish_error,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();

  if (!text) return "暂无错误详情";
  if (text.includes("creator") || text.includes("publish") || text.includes("image bytes")) {
    return "创作者平台或发布素材问题";
  }
  if (text.includes("llm") || text.includes("json") || text.includes("model")) {
    return "LLM 生成或解析问题";
  }
  if (text.includes("collect") || text.includes("comment") || text.includes("cookie") || text.includes("spider")) {
    return "采集或 Cookie 问题";
  }
  if (text.includes("compliance") || text.includes("risk")) {
    return "合规拦截";
  }
  return "未分类失败，请查看错误详情";
}

function runErrorDetail(run) {
  return (
    run?.error ||
    run?.summary?.creator_publish_error ||
    run?.state?.error ||
    run?.state?.creator_publish_error ||
    ""
  );
}

function renderRunDiagnostics(run) {
  const request = run.request || {};
  const errorDetail = runErrorDetail(run);
  const isFailed = run.status === "failed" || Boolean(errorDetail);
  const failureHtml = isFailed
    ? `<div class="diagnostic-alert">
        <strong>${escapeHtml(diagnoseRunFailure(run))}</strong>
        <p><span>错误详情</span>${escapeHtml(errorDetail || "任务失败，但没有返回详细错误")}</p>
      </div>`
    : "";

  elements.runDiagnostics.innerHTML = `
    <div class="diagnostics-head">
      <h3>运行诊断</h3>
      <span class="mini-pill ${statusClass(run.status)}">${escapeHtml(run.status || "-")}</span>
    </div>
    <div class="diagnostics-grid">
      ${metric("主题", request.topic)}
      ${metric("目标用户", request.target_user)}
      ${metric("形式", request.format)}
      ${metric("引擎", request.engine)}
      ${metric("采集数量", request.collect_limit)}
      ${metric("创建时间", compactTime(run.created_at))}
      ${metric("更新时间", compactTime(run.updated_at))}
      ${metric("任务 ID", run.run_id)}
    </div>
    ${failureHtml}
    <div class="diagnostic-actions">
      <button class="ghost-button" type="button" id="resubmitRunButton">用此任务参数重新提交</button>
    </div>
  `;

  const resubmitButton = $("#resubmitRunButton");
  if (resubmitButton) {
    resubmitButton.addEventListener("click", () => {
      resubmitRunFromCurrent();
    });
  }
}

function renderQueue(queue) {
  elements.queueStrip.innerHTML = `
    <span>等待 ${queue.queued_count ?? 0}</span>
    <span>运行 ${queue.running_count ?? 0}</span>
  `;
  const queued = queue.queued_run_ids || [];
  const running = queue.running_run_ids || [];
  elements.queueDetail.innerHTML = `
    <p><strong>运行中</strong></p>
    <p class="path-line">${running.length ? running.map(escapeHtml).join("<br>") : "无"}</p>
    <p><strong>等待中</strong></p>
    <p class="path-line">${queued.length ? queued.map(escapeHtml).join("<br>") : "无"}</p>
  `;
}

function compactTime(value) {
  if (!value) return "-";
  return String(value).replace("T", " ");
}

function renderRunList(runs) {
  if (!runs.length) {
    elements.runList.innerHTML = `<div class="run-item"><p class="muted">暂无运行记录</p></div>`;
    return;
  }

  elements.runList.innerHTML = runs
    .map((run) => {
      const request = run.request || {};
      const summary = run.summary || {};
      return `
        <div class="run-item" data-run-id="${escapeHtml(run.run_id)}">
          <div class="run-title">
            <strong>${escapeHtml(request.topic || run.run_id)}</strong>
            <span class="mini-pill ${statusClass(run.status)}">${escapeHtml(run.status)}</span>
          </div>
          <p class="muted">${escapeHtml(request.format || "-")} · ${escapeHtml(summary.content_type || "-")} · ${escapeHtml(compactTime(run.updated_at || run.created_at))}</p>
        </div>
      `;
    })
    .join("");

  elements.runList.querySelectorAll(".run-item").forEach((item) => {
    item.addEventListener("click", () => loadRun(item.dataset.runId, true));
  });
}

function renderSummary(run) {
  const summary = run.summary || {};
  elements.currentStatus.textContent = run.status || "未选择";
  elements.currentStatus.className = `status-pill ${statusClass(run.status)}`;
  elements.summaryGrid.innerHTML = [
    metric("形式", summary.content_format),
    metric("类型", summary.content_type),
    metric("合规", summary.compliance_risk_level),
    metric("笔记", summary.raw_notes_count),
    metric("评论", summary.raw_comments_count),
    metric("痛点", summary.pain_points_count),
    metric("记忆", summary.successful_patterns_count),
    metric("LLM", summary.llm_generation?.enabled ? "已启用" : "未启用"),
    metric("人审", summary.human_approved ? "通过" : "待审"),
    metric("发布", summary.publish_status),
    metric("发布图片", summary.creator_images_count),
    metric("创作发布", creatorPublishStatusLabel(summary.creator_publish_status)),
    metric("平台笔记", summary.creator_note_id),
  ].join("");
}

function renderReviewActions(run) {
  const summary = run.summary || {};
  const hasDraft = Object.keys(run.content || {}).length > 0;
  const showReviewArea = run.status === "success" && hasDraft;
  const canReview =
    showReviewArea &&
    hasDraft &&
    summary.publish_status === "pending" &&
    summary.post_id == null &&
    summary.compliance_risk_level !== "high";
  const canBindAssets = canReview && summary.content_format === "image_text";

  elements.reviewActions.hidden = !showReviewArea;
  elements.approveRunButton.disabled = !canReview;
  elements.rejectRunButton.disabled = !canReview;
  elements.creatorAssetInput.disabled = !canBindAssets;
  elements.attachCreatorAssetsButton.disabled = !canBindAssets;
  elements.creatorPublishCheckbox.disabled = !canReview;
  if (!canReview) {
    elements.creatorAssetInput.value = "";
    elements.creatorPublishCheckbox.checked = false;
  }

  const creatorError = creatorPublishError(summary);
  if (creatorError) {
    setNotice(elements.reviewNotice, creatorError, true);
  } else if (summary.publish_status === "success") {
    setNotice(elements.reviewNotice, "已保存草稿并写入运营记忆");
  } else if (summary.publish_status === "rejected") {
    setNotice(elements.reviewNotice, "人工审核不通过，草稿未保存", true);
  } else if (summary.compliance_risk_level === "high") {
    setNotice(elements.reviewNotice, "合规风险高，不能直接审核通过", true);
  } else if (canReview) {
    setNotice(elements.reviewNotice, "等待人工审核");
  }
}

function renderImageText(content) {
  const pages = content.image_page_plan || [];
  const prompts = content.image_prompts || [];
  return `
    <div class="draft-section">
      <h3>标题</h3>
      <ul>${(content.titles || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
    </div>
    <div class="draft-section">
      <h3>封面文案</h3>
      <ul>${(content.cover_texts || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
    </div>
    <div class="draft-section">
      <h3>正文</h3>
      <p class="body-text">${escapeHtml(content.body || "")}</p>
    </div>
    <div class="draft-section">
      <h3>图片页规划</h3>
      <ul>${pages.map((page) => `<li>P${escapeHtml(page.page)}：${escapeHtml(page.title)} - ${escapeHtml(page.text)}</li>`).join("")}</ul>
    </div>
    <div class="draft-section">
      <h3>图片提示词</h3>
      <ul>${prompts.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
    </div>
    <div class="draft-section">
      <h3>标签与评论引导</h3>
      <p>${(content.tags || []).map((tag) => `#${escapeHtml(tag)}`).join(" ")}</p>
      <p>${escapeHtml(content.comment_call || "")}</p>
    </div>
  `;
}

function renderVideo(content) {
  const script = content.video_script || {};
  const shotPlan = script.shot_plan || [];
  return `
    <div class="draft-section"><h3>标题</h3><p>${escapeHtml(script.title || "")}</p></div>
    <div class="draft-section"><h3>开场钩子</h3><p>${escapeHtml(script.hook || "")}</p></div>
    <div class="draft-section"><h3>开场口播</h3><p>${escapeHtml(script.opening || "")}</p></div>
    <div class="draft-section">
      <h3>口播要点</h3>
      <ul>${(script.talking_points || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
    </div>
    <div class="draft-section">
      <h3>分镜规划</h3>
      <ul>${shotPlan.map((item) => `<li>镜头${escapeHtml(item.scene)}：${escapeHtml(item.visual)}｜屏幕文字：${escapeHtml(item.text)}</li>`).join("")}</ul>
    </div>
    <div class="draft-section">
      <h3>字幕与封面</h3>
      <ul>${(script.subtitle_plan || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
      <p>${escapeHtml(script.cover_text || "")}</p>
    </div>
    <div class="draft-section">
      <h3>标签与评论引导</h3>
      <p>${(content.tags || []).map((tag) => `#${escapeHtml(tag)}`).join(" ")}</p>
      <p>${escapeHtml(content.comment_call || "")}</p>
      <p class="muted">${escapeHtml(script.compliance_note || "")}</p>
    </div>
  `;
}

function renderInsights(insights) {
  const painPoints = insights.pain_points || [];
  const commentInsights = insights.comment_insights || [];
  const errors = insights.comment_fetch_errors || [];
  const painHtml = painPoints.length
    ? painPoints
        .map((item) => `<div class="insight-item"><h3>${escapeHtml(item.pain || item)}</h3><p>${escapeHtml(item.evidence || "")}</p></div>`)
        .join("")
    : `<div class="insight-item"><p class="muted">暂无痛点数据</p></div>`;
  const commentsHtml = commentInsights
    .map((item) => {
      const comments = item.evidence_comments || [];
      return `<div class="insight-item"><h3>${escapeHtml(item.pain || "")}</h3><ul>${comments.map((comment) => `<li>${escapeHtml(comment)}</li>`).join("")}</ul></div>`;
    })
    .join("");
  const errorsHtml = errors.length
    ? `<div class="insight-item"><h3>采集错误</h3><ul>${errors.map((error) => `<li>${escapeHtml(JSON.stringify(error))}</li>`).join("")}</ul></div>`
    : "";
  elements.insightsTab.innerHTML = painHtml + commentsHtml + errorsHtml;
}

function renderRun(run) {
  state.currentRun = run;
  renderSummary(run);
  renderRunDiagnostics(run);
  renderReviewActions(run);

  const content = run.content || {};
  if (run.summary?.content_format === "video") {
    elements.draftTab.innerHTML = renderVideo(content);
  } else if (Object.keys(content).length) {
    elements.draftTab.innerHTML = renderImageText(content);
  } else {
    elements.draftTab.innerHTML = `<div class="draft-section"><p class="muted">任务尚未产出草稿</p></div>`;
  }

  renderInsights(run.insights || {});
  elements.rawTab.textContent = JSON.stringify(run, null, 2);

  const postId = run.summary?.post_id || run.paths?.post_id;
  if (postId) {
    elements.performanceForm.elements.post_id.value = postId;
  }
}

async function loadRun(runId, keepPolling = false) {
  const data = await apiGet(`/runs/${encodeURIComponent(runId)}`);
  state.currentRunId = runId;
  renderRun(data.run);
  if (keepPolling && ["queued", "running"].includes(data.run.status)) {
    startRunPolling(runId);
  }
  return data.run;
}

function startRunPolling(runId) {
  if (state.pollTimer) {
    clearInterval(state.pollTimer);
  }
  state.pollTimer = setInterval(async () => {
    try {
      const run = await loadRun(runId, false);
      await refreshShell();
      if (!["queued", "running"].includes(run.status)) {
        clearInterval(state.pollTimer);
        state.pollTimer = null;
      }
    } catch (error) {
      setNotice(elements.formNotice, error.message, true);
    }
  }, 2000);
}

async function refreshShell() {
  const [queue, runs, memory] = await Promise.all([
    apiGet("/queue"),
    apiGet("/runs?limit=12"),
    apiGet("/memory/records?limit=8"),
  ]);
  renderQueue(queue);
  renderRunList(runs.runs || []);
  renderMemory(memory.records || []);
}

function renderMemory(records) {
  if (!records.length) {
    elements.memoryList.innerHTML = `<div class="memory-item"><p class="muted">暂无运营记忆</p></div>`;
    return;
  }

  elements.memoryList.innerHTML = records
    .map((record) => `
      <div class="memory-item" data-record-id="${escapeHtml(record.record_id || "")}" data-post-id="${escapeHtml(record.post_id || "")}" data-creator-note-id="${escapeHtml(record.creator_note_id || "")}">
        <div class="memory-title">
          <strong>${escapeHtml(record.title || record.topic || record.record_id)}</strong>
          <span class="mini-pill">${escapeHtml(record.performance_score ?? 0)}</span>
        </div>
        <p class="muted">${escapeHtml(record.content_format || "-")} · ${escapeHtml(record.content_type || "-")} · ${escapeHtml(record.status || "-")}</p>
        ${memoryMetaGrid(record)}
        <p>${escapeHtml(record.review_summary || "")}</p>
        <p class="path-line">${escapeHtml(record.post_id || "")}</p>
        <div class="memory-actions">
          <button class="ghost-button memory-action-button" type="button">用这条记录录入表现</button>
        </div>
      </div>
    `)
    .join("");

  elements.memoryList.querySelectorAll(".memory-action-button").forEach((button) => {
    button.addEventListener("click", () => {
      const item = button.closest(".memory-item");
      fillPerformanceFromMemoryRecord({
        recordId: item?.dataset.recordId,
        postId: item?.dataset.postId,
        creatorNoteId: item?.dataset.creatorNoteId,
      });
    });
  });
}

function renderCreatorNotes(notes) {
  if (!notes.length) {
    elements.creatorNotesList.innerHTML = `<div class="creator-note-item"><p class="muted">暂无平台作品</p></div>`;
    return;
  }

  elements.creatorNotesList.innerHTML = notes
    .map((note) => {
      const noteId = note.note_id || "";
      return `
        <button class="creator-note-item" type="button" data-note-id="${escapeHtml(noteId)}">
          <strong>${escapeHtml(note.title || noteId || "未命名作品")}</strong>
          <span>${escapeHtml(noteId)}</span>
          <span class="muted">${escapeHtml(note.visibility || "-")}</span>
        </button>
      `;
    })
    .join("");

  elements.creatorNotesList.querySelectorAll(".creator-note-item").forEach((item) => {
    item.addEventListener("click", () => {
      elements.performanceForm.elements.creator_note_id.value = item.dataset.noteId || "";
      setNotice(elements.performanceNotice, `已选择平台笔记：${item.dataset.noteId || "-"}`);
    });
  });
}

async function syncCreatorNotes() {
  elements.syncCreatorNotesButton.disabled = true;
  setNotice(elements.performanceNotice, "正在同步作品列表");
  try {
    const data = await apiGet("/creator/notes?limit=20");
    const creatorNotes = data.creator_notes || {};
    if (creatorNotes.ok === false) {
      throw new Error(creatorNotes.error || "同步作品列表失败");
    }
    renderCreatorNotes(creatorNotes.notes || []);
    setNotice(elements.performanceNotice, `已同步 ${(creatorNotes.notes || []).length} 条作品`);
  } catch (error) {
    setNotice(elements.performanceNotice, error.message, true);
  } finally {
    elements.syncCreatorNotesButton.disabled = false;
  }
}

function fileToCreatorAssetPayload(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = String(reader.result || "");
      const contentBase64 = result.includes(",") ? result.split(",", 2)[1] : result;
      resolve({
        filename: file.name,
        content_base64: contentBase64,
      });
    };
    reader.onerror = () => reject(new Error(`读取图片失败：${file.name}`));
    reader.readAsDataURL(file);
  });
}

async function attachCreatorAssets() {
  if (!state.currentRunId) {
    setNotice(elements.reviewNotice, "请先选择一个任务", true);
    return;
  }

  const files = Array.from(elements.creatorAssetInput.files || []);
  if (!files.length) {
    setNotice(elements.reviewNotice, "请先选择发布图片", true);
    return;
  }

  elements.attachCreatorAssetsButton.disabled = true;
  elements.creatorAssetInput.disabled = true;
  setNotice(elements.reviewNotice, "正在绑定发布图片");
  try {
    const images = await Promise.all(files.map(fileToCreatorAssetPayload));
    const data = await apiPost(`/runs/${encodeURIComponent(state.currentRunId)}/creator-assets`, { images });
    renderRun(data.run);
    elements.creatorAssetInput.value = "";
    await refreshShell();
    setNotice(elements.reviewNotice, `已绑定 ${data.run.summary?.creator_images_count ?? images.length} 张发布图片`);
  } catch (error) {
    setNotice(elements.reviewNotice, error.message, true);
  } finally {
    renderReviewActions(state.currentRun || {});
  }
}

function activateTab(tabName) {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.tab === tabName);
  });
  document.querySelectorAll(".tab-view").forEach((view) => {
    view.classList.remove("active");
  });
  $(`#${tabName}Tab`).classList.add("active");
}

elements.runForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(elements.runForm);
  const payload = {
    topic: form.get("topic"),
    target_user: form.get("target_user"),
    format: form.get("format"),
    engine: form.get("engine"),
    collect_limit: Number(form.get("collect_limit") || 5),
    approve: elements.runForm.elements.approve.checked,
  };

  elements.submitButton.disabled = true;
  setNotice(elements.formNotice, "任务已提交");
  try {
    const data = await apiPost("/runs", payload);
    state.currentRunId = data.run.run_id;
    renderRun(data.run);
    await refreshShell();
    startRunPolling(data.run.run_id);
    setNotice(elements.formNotice, `任务 ${data.run.run_id} 已进入队列`);
  } catch (error) {
    setNotice(elements.formNotice, error.message, true);
  } finally {
    elements.submitButton.disabled = false;
  }
});

elements.performanceForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(elements.performanceForm);
  const payload = {
    post_id: form.get("post_id"),
    creator_note_id: form.get("creator_note_id"),
    views: Number(form.get("views") || 0),
    likes: Number(form.get("likes") || 0),
    collects: Number(form.get("collects") || 0),
    comments: Number(form.get("comments") || 0),
    follows: Number(form.get("follows") || 0),
  };

  setNotice(elements.performanceNotice, "正在录入");
  try {
    const data = await apiPost("/performance", payload);
    setNotice(elements.performanceNotice, `已更新：${data.updated_record.record_id}`);
    await refreshShell();
  } catch (error) {
    setNotice(elements.performanceNotice, error.message, true);
  }
});

elements.syncCreatorNotesButton.addEventListener("click", () => {
  syncCreatorNotes();
});

async function resubmitRunFromCurrent() {
  if (!state.currentRun) {
    setNotice(elements.formNotice, "请先选择一个任务", true);
    return;
  }

  const request = state.currentRun?.request || {};
  const payload = {
    topic: request.topic,
    target_user: request.target_user,
    format: request.format,
    engine: request.engine,
    collect_limit: Number(request.collect_limit || 5),
    approve: Boolean(request.approve),
  };

  setNotice(elements.formNotice, "正在用原任务参数重新提交");
  try {
    const data = await apiPost("/runs", payload);
    state.currentRunId = data.run.run_id;
    renderRun(data.run);
    await refreshShell();
    startRunPolling(data.run.run_id);
    setNotice(elements.formNotice, `新任务 ${data.run.run_id} 已进入队列`);
  } catch (error) {
    setNotice(elements.formNotice, error.message, true);
  }
}

async function submitReviewAction(action) {
  if (!state.currentRunId) {
    setNotice(elements.reviewNotice, "请先选择一个任务", true);
    return;
  }

  const isApprove = action === "approve";
  elements.approveRunButton.disabled = true;
  elements.rejectRunButton.disabled = true;
  elements.creatorAssetInput.disabled = true;
  elements.attachCreatorAssetsButton.disabled = true;
  elements.creatorPublishCheckbox.disabled = true;
  setNotice(elements.reviewNotice, isApprove ? "正在保存草稿" : "正在驳回草稿");

  try {
    const reviewPayload = {
      feedback: isApprove ? "前端人工审核通过。" : "前端人工审核不通过。",
    };
    if (isApprove && elements.creatorPublishCheckbox.checked) {
      reviewPayload.creator_publish = true;
      reviewPayload.creator_publish_private = true;
      reviewPayload.creator_human_confirmed = true;
    }
    const data = await apiPost(`/runs/${encodeURIComponent(state.currentRunId)}/${action}`, reviewPayload);
    renderRun(data.run);
    elements.creatorPublishCheckbox.checked = false;
    await refreshShell();
    setNotice(elements.reviewNotice, isApprove ? "已保存并写入运营记忆" : "已标记为审核不通过");
  } catch (error) {
    setNotice(elements.reviewNotice, error.message, true);
  } finally {
    renderReviewActions(state.currentRun || {});
  }
}

elements.attachCreatorAssetsButton.addEventListener("click", () => {
  attachCreatorAssets();
});
elements.approveRunButton.addEventListener("click", () => submitReviewAction("approve"));
elements.rejectRunButton.addEventListener("click", () => submitReviewAction("reject"));

elements.refreshButton.addEventListener("click", async () => {
  await refreshShell();
  if (state.currentRunId) {
    await loadRun(state.currentRunId, true);
  }
});

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => activateTab(tab.dataset.tab));
});

async function boot() {
  try {
    const health = await apiGet("/health");
    elements.serviceStatus.textContent = `${health.service} · ${health.time}`;
    await refreshShell();
  } catch (error) {
    elements.serviceStatus.textContent = error.message;
  }
}

setInterval(() => {
  refreshShell().catch(() => {});
}, 5000);

boot();
