(() => {
  const state = {
    role: "USER",
    ingredients: [],
    recipes: [],
  };

  const roleSelect = document.getElementById("roleSelect");
  const alertBox = document.getElementById("alertBox");
  const alertMessage = document.getElementById("alertMessage");
  const alertClose = document.getElementById("alertClose");
  const logDateInput = document.getElementById("logDateInput");

  // Default date to today
  logDateInput.value = new Date().toISOString().slice(0, 10);

  function getHeaders() {
    return {
      "Content-Type": "application/json",
      "X-User-Role": state.role,
      "X-User-Id": state.role === "ADMIN" ? "2" : "1",
    };
  }

  function showAlert(message, type = "error") {
    alertMessage.textContent = message;
    alertBox.className = `alert alert-${type}`;
  }

  function hideAlert() {
    alertBox.className = "alert hidden";
  }

  alertClose.addEventListener("click", hideAlert);

  function extractErrorMessage(data, statusCode) {
    if (!data) return `Hiba történt (HTTP ${statusCode}).`;
    if (typeof data.detail === "string") return `HTTP ${statusCode}: ${data.detail}`;
    if (Array.isArray(data.detail)) {
      const msgs = data.detail.map((item) => item.msg || JSON.stringify(item));
      return `HTTP ${statusCode}: ${msgs.join(" | ")}`;
    }
    return `HTTP ${statusCode}: ${JSON.stringify(data)}`;
  }

  async function apiFetch(url, options = {}) {
    const resp = await fetch(url, {
      ...options,
      headers: {
        ...getHeaders(),
        ...(options.headers || {}),
      },
    });
    if (resp.status === 204) return null;
    const data = await resp.json().catch(() => null);
    if (!resp.ok) {
      const msg = extractErrorMessage(data, resp.status);
      showAlert(msg, "error");
      throw new Error(msg);
    }
    return data;
  }

  // Tabs
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById(btn.dataset.tab).classList.add("active");
      hideAlert();
    });
  });

  // Role switcher
  roleSelect.addEventListener("change", () => {
    state.role = roleSelect.value;
    hideAlert();
    loadProfile();
    loadBanned();
    loadDailySummary();
  });

  // -------------------------------------------------------------------------
  // Tab 1: Ingredients
  // -------------------------------------------------------------------------
  function renderIngredientsTable(list) {
    const tbody = document.getElementById("ingredientsTableBody");
    tbody.innerHTML = "";
    list.forEach((ing) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><strong>${escapeHtml(ing.name)}</strong></td>
        <td>${ing.energy_kcal}</td>
        <td>${ing.protein}</td>
        <td>${ing.carbs} <span class="hint">(${ing.sugar})</span></td>
        <td>${ing.fat} <span class="hint">(${ing.saturated_fat} / ${ing.unsaturated_fat})</span></td>
        <td>${ing.fiber}</td>
        <td>${ing.salt}</td>
      `;
      tbody.appendChild(tr);
    });
  }

  function populateIngredientSelects() {
    const selects = [
      document.getElementById("bannedIngredientSelect"),
      document.getElementById("logIngredientSelect"),
      ...document.querySelectorAll(".recipe-item-select"),
    ];
    selects.forEach((sel) => {
      if (!sel) return;
      const prev = sel.value;
      sel.innerHTML = state.ingredients
        .map((i) => `<option value="${i.id}">${escapeHtml(i.name)}</option>`)
        .join("");
      if (prev) sel.value = prev;
    });
  }

  async function loadIngredients(search = "") {
    const qs = search ? `?search=${encodeURIComponent(search)}` : "";
    const data = await apiFetch(`/api/ingredients${qs}`);
    if (!search) {
      state.ingredients = data;
      populateIngredientSelects();
    }
    renderIngredientsTable(data);
  }

  document.getElementById("ingredientSearch").addEventListener("input", (e) => {
    loadIngredients(e.target.value.trim());
  });

  document.getElementById("ingredientForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    hideAlert();
    const fd = new FormData(e.target);
    const payload = Object.fromEntries(fd.entries());
    try {
      await apiFetch("/api/ingredients", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      e.target.reset();
      showAlert("Alapanyag sikeresen mentve!", "success");
      await loadIngredients();
    } catch (_) {
      // Error already shown in alertBox
    }
  });

  // -------------------------------------------------------------------------
  // Tab 2: Profile & Banned Ingredients
  // -------------------------------------------------------------------------
  async function loadProfile() {
    const data = await apiFetch("/api/profile");
    document.getElementById("dailyCarbLimit").value = data.daily_carb_limit;
    document.getElementById("dailyProteinTarget").value = data.daily_protein_target;
    document.getElementById("dailyFatTarget").value = data.daily_fat_target;
  }

  document.getElementById("profileForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    hideAlert();
    const fd = new FormData(e.target);
    const payload = Object.fromEntries(fd.entries());
    try {
      await apiFetch("/api/profile", {
        method: "PUT",
        body: JSON.stringify(payload),
      });
      showAlert("Profil sikeresen frissítve!", "success");
      await loadDailySummary();
    } catch (_) {}
  });

  async function loadBanned() {
    const list = await apiFetch("/api/profile/banned");
    const ul = document.getElementById("bannedList");
    ul.innerHTML = "";
    if (!list.length) {
      ul.innerHTML = `<li style="background:#f8fafc;border-color:#e2e8f0;color:#64748b;">Nincs tiltólistás alapanyag.</li>`;
      return;
    }
    list.forEach((item) => {
      const li = document.createElement("li");
      li.innerHTML = `
        <span><strong>${escapeHtml(item.ingredient_name)}</strong></span>
        <button class="btn btn-secondary btn-sm" data-id="${item.ingredient_id}">Törlés</button>
      `;
      li.querySelector("button").addEventListener("click", async () => {
        hideAlert();
        await apiFetch(`/api/profile/banned/${item.ingredient_id}`, { method: "DELETE" });
        await loadBanned();
      });
      ul.appendChild(li);
    });
  }

  document.getElementById("bannedForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    hideAlert();
    const ingredientId = Number(document.getElementById("bannedIngredientSelect").value);
    try {
      await apiFetch("/api/profile/banned", {
        method: "POST",
        body: JSON.stringify({ ingredient_id: ingredientId }),
      });
      showAlert("Alapanyag hozzáadva a tiltólistához.", "success");
      await loadBanned();
    } catch (_) {}
  });

  // -------------------------------------------------------------------------
  // Tab 3: Recipes & Daily Logs
  // -------------------------------------------------------------------------
  function renderRecipes(list) {
    document.getElementById("recipeCount").textContent = list.length;
    const container = document.getElementById("recipesList");
    container.innerHTML = "";
    list.forEach((r) => {
      const m = r.per_serving_macros;
      const div = document.createElement("div");
      div.className = "recipe-card";
      div.innerHTML = `
        <div>
          <div class="recipe-title">${escapeHtml(r.name)}</div>
          <div class="recipe-meta">
            1 adag (${r.servings} adagból):
            <strong>${m.carbs} g CH</strong> (${m.sugar} g cukor) &bull;
            ${m.protein} g fehérje &bull; ${m.fat} g zsír &bull; ${m.salt} g só &bull; ${m.energy_kcal} kcal
          </div>
        </div>
        <button class="btn btn-primary btn-sm" type="button">Naplózás (1 adag)</button>
      `;
      div.querySelector("button").addEventListener("click", () => logRecipe(r.id));
      container.appendChild(div);
    });
  }

  async function loadRecipes(search = "") {
    const qs = search ? `?search=${encodeURIComponent(search)}` : "";
    const data = await apiFetch(`/api/recipes${qs}`);
    state.recipes = data;
    renderRecipes(data);
  }

  document.getElementById("recipeSearch").addEventListener("input", (e) => {
    loadRecipes(e.target.value.trim());
  });

  function addRecipeItemRow() {
    const container = document.getElementById("recipeItemsContainer");
    const row = document.createElement("div");
    row.className = "recipe-item-row";
    const options = state.ingredients
      .map((i) => `<option value="${i.id}">${escapeHtml(i.name)}</option>`)
      .join("");
    row.innerHTML = `
      <select class="recipe-item-select" required>${options}</select>
      <input type="number" step="0.01" class="recipe-item-weight" value="100.00" placeholder="g" required />
      <button type="button" class="btn btn-secondary btn-sm remove-row">&times;</button>
    `;
    row.querySelector(".remove-row").addEventListener("click", () => row.remove());
    container.appendChild(row);
  }

  document.getElementById("addRecipeItemBtn").addEventListener("click", addRecipeItemRow);

  document.getElementById("recipeForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    hideAlert();
    const rows = document.querySelectorAll("#recipeItemsContainer .recipe-item-row");
    const items = Array.from(rows).map((row) => ({
      ingredient_id: Number(row.querySelector(".recipe-item-select").value),
      weight_g: row.querySelector(".recipe-item-weight").value,
    }));
    const payload = {
      name: document.getElementById("recipeName").value.trim(),
      servings: document.getElementById("recipeServings").value,
      items,
    };
    try {
      await apiFetch("/api/recipes", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      document.getElementById("recipeName").value = "";
      showAlert("Recept sikeresen létrehozva!", "success");
      await loadRecipes(document.getElementById("recipeSearch").value.trim());
    } catch (_) {}
  });

  async function logRecipe(recipeId) {
    hideAlert();
    try {
      await apiFetch("/api/logs", {
        method: "POST",
        body: JSON.stringify({
          log_date: logDateInput.value,
          recipe_id: recipeId,
          servings: "1.00",
        }),
      });
      showAlert("Recept (1 adag) naplózva!", "success");
      await loadDailySummary();
    } catch (_) {}
  }

  document.getElementById("logIngredientForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    hideAlert();
    const payload = {
      log_date: logDateInput.value,
      ingredient_id: Number(document.getElementById("logIngredientSelect").value),
      weight_g: document.getElementById("logIngredientWeight").value,
      meal_name: document.getElementById("logMealName").value.trim() || null,
    };
    try {
      await apiFetch("/api/logs", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      document.getElementById("logMealName").value = "";
      showAlert("Étkezés sikeresen naplózva!", "success");
      await loadDailySummary();
    } catch (_) {}
  });

  async function loadDailySummary() {
    const date = logDateInput.value;
    const summary = await apiFetch(`/api/logs/${date}`);
    const badge = document.getElementById("dailyStatusBadge");
    badge.textContent = summary.status;
    badge.className =
      summary.status === "MEGFELELŐ"
        ? "status-badge status-ok"
        : "status-badge status-exceeded";

    document.getElementById("kpiCarbs").textContent = `${summary.totals.carbs} / ${summary.daily_carb_limit} g`;
    document.getElementById("kpiRemaining").textContent = `${summary.remaining_carbs} g`;
    document.getElementById("kpiSugar").textContent = `${summary.totals.sugar} g`;
    document.getElementById("kpiProtein").textContent = `${summary.totals.protein} g`;
    document.getElementById("kpiFat").textContent = `${summary.totals.fat} g`;
    document.getElementById("kpiSalt").textContent = `${summary.totals.salt} g`;

    const tbody = document.getElementById("dailyLogsBody");
    tbody.innerHTML = "";
    if (!summary.entries.length) {
      tbody.innerHTML = `<tr><td colspan="6" style="color:#64748b;">Még nincs naplózott tétel ezen a napon.</td></tr>`;
      return;
    }
    summary.entries.forEach((entry) => {
      const m = entry.macros;
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><strong>${escapeHtml(entry.meal_name)}</strong></td>
        <td>${m.carbs}</td>
        <td>${m.sugar}</td>
        <td>${m.protein}</td>
        <td>${m.fat}</td>
        <td>${m.salt}</td>
      `;
      tbody.appendChild(tr);
    });
  }

  logDateInput.addEventListener("change", loadDailySummary);

  function escapeHtml(str) {
    return String(str)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  // Initial load
  (async function init() {
    await loadIngredients();
    addRecipeItemRow();
    await Promise.all([loadProfile(), loadBanned(), loadRecipes(), loadDailySummary()]);
  })();
})();
