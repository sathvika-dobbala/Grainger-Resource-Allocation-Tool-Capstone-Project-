(function () {
  "use strict";

  /** DOM Elements */
  const pageTitle = document.getElementById("pageTitle");
  const skillsTableBody = document.getElementById("skillsTableBody");
  const addSkillForm = document.getElementById("addSkillForm");

  /** Get employee ID from URL */
  const url = new URL(window.location.href);
  const empId = url.searchParams.get("id");

  if (!empId) {
    alert("❌ No employee ID provided");
    window.location.href = "./manager-portal.html";
    return;
  }

  /** API Helpers */
  async function fetchEmployeeSkills() {
    const res = await fetch(`/employees/${empId}/skills`);
    if (!res.ok) {
      alert("❌ Error loading employee skills");
      return null;
    }
    return await res.json();
  }

  async function addSkill(skillData) {
    const res = await fetch(`/employees/${empId}/skills`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(skillData),
    });
    return await res.json();
  }

  async function updateSkill(skillId, skillData) {
    const res = await fetch(`/employees/${empId}/skills/${skillId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(skillData),
    });
    return await res.json();
  }

  async function deleteSkill(skillId) {
    const res = await fetch(`/employees/${empId}/skills/${skillId}`, {
      method: "DELETE",
    });
    return await res.json();
  }

  /** Rendering */
  async function render() {
    const data = await fetchEmployeeSkills();
    if (!data) return;

    const { employee, skills } = data;

    // Update page title
    pageTitle.textContent = `Skills for ${employee.firstname || ""} ${employee.lastname || ""}`;

    // Render skills table
    if (skills.length === 0) {
      skillsTableBody.innerHTML = `
        <tr>
          <td colspan="4" class="empty">No skills added yet. Add one below!</td>
        </tr>
      `;
      return;
    }

    skillsTableBody.innerHTML = skills.map(toSkillRow).join("");

    // Attach event listeners to edit/delete buttons
    attachEventListeners();
  }

  function toSkillRow(skill) {
    return `
      <tr data-skill-id="${skill.skillID}">
        <td>${escapeHtml(skill.skillName)}</td>
        <td>
          <input type="number" 
                 class="proficiency-input" 
                 min="0" 
                 max="10" 
                 value="${skill.profiencylevel || ""}"
                 data-original="${skill.profiencylevel || ""}"
                 disabled>
        </td>
        <td>
          <input type="text" 
                 class="evidence-input" 
                 value="${escapeHtml(skill.evidence || "")}"
                 data-original="${escapeHtml(skill.evidence || "")}"
                 disabled>
        </td>
        <td>
          <button class="edit-btn secondary" type="button">Edit</button>
          <button class="save-btn" type="button" style="display:none;">Save</button>
          <button class="cancel-btn secondary" type="button" style="display:none;">Cancel</button>
          <button class="delete-btn danger" type="button">Delete</button>
        </td>
      </tr>
    `;
  }

  function attachEventListeners() {
    // Edit buttons
    document.querySelectorAll(".edit-btn").forEach((btn) => {
      btn.addEventListener("click", handleEdit);
    });

    // Save buttons
    document.querySelectorAll(".save-btn").forEach((btn) => {
      btn.addEventListener("click", handleSave);
    });

    // Cancel buttons
    document.querySelectorAll(".cancel-btn").forEach((btn) => {
      btn.addEventListener("click", handleCancel);
    });

    // Delete buttons
    document.querySelectorAll(".delete-btn").forEach((btn) => {
      btn.addEventListener("click", handleDelete);
    });
  }

  function handleEdit(e) {
    const row = e.target.closest("tr");
    const proficiencyInput = row.querySelector(".proficiency-input");
    const evidenceInput = row.querySelector(".evidence-input");
    const editBtn = row.querySelector(".edit-btn");
    const saveBtn = row.querySelector(".save-btn");
    const cancelBtn = row.querySelector(".cancel-btn");
    const deleteBtn = row.querySelector(".delete-btn");

    // Enable inputs
    proficiencyInput.disabled = false;
    evidenceInput.disabled = false;
    proficiencyInput.classList.add("edit-mode");
    evidenceInput.classList.add("edit-mode");

    // Toggle buttons
    editBtn.style.display = "none";
    deleteBtn.style.display = "none";
    saveBtn.style.display = "inline-block";
    cancelBtn.style.display = "inline-block";
  }

  async function handleSave(e) {
    const row = e.target.closest("tr");
    const skillId = row.dataset.skillId;
    const proficiencyInput = row.querySelector(".proficiency-input");
    const evidenceInput = row.querySelector(".evidence-input");

    const proficiency = parseInt(proficiencyInput.value);
    const evidence = evidenceInput.value.trim();

    // Validation
    if (!proficiency || proficiency < 1 || proficiency > 10) {
      alert("⚠️ Proficiency must be between 1 and 10");
      return;
    }

    // Update via API
    await updateSkill(skillId, {
      profiencylevel: proficiency,
      evidence: evidence,
    });

    alert("✅ Skill updated successfully!");
    await render();
  }

  function handleCancel(e) {
    const row = e.target.closest("tr");
    const proficiencyInput = row.querySelector(".proficiency-input");
    const evidenceInput = row.querySelector(".evidence-input");

    // Restore original values
    proficiencyInput.value = proficiencyInput.dataset.original;
    evidenceInput.value = evidenceInput.dataset.original;

    // Disable inputs
    proficiencyInput.disabled = true;
    evidenceInput.disabled = true;
    proficiencyInput.classList.remove("edit-mode");
    evidenceInput.classList.remove("edit-mode");

    // Toggle buttons
    const editBtn = row.querySelector(".edit-btn");
    const saveBtn = row.querySelector(".save-btn");
    const cancelBtn = row.querySelector(".cancel-btn");
    const deleteBtn = row.querySelector(".delete-btn");

    editBtn.style.display = "inline-block";
    deleteBtn.style.display = "inline-block";
    saveBtn.style.display = "none";
    cancelBtn.style.display = "none";
  }

  async function handleDelete(e) {
    const row = e.target.closest("tr");
    const skillId = row.dataset.skillId;
    const skillName = row.querySelector("td:first-child").textContent;

    if (!confirm(`❌ Are you sure you want to delete the skill: ${skillName}?`)) {
      return;
    }

    await deleteSkill(skillId);
    alert("🗑️ Skill deleted successfully!");
    await render();
  }

  /** Add Skill Form */
  addSkillForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    const formData = new FormData(addSkillForm);
    const skillData = {
      skillName: formData.get("skillName"),
      profiencylevel: parseInt(formData.get("profiencylevel")),
      evidence: formData.get("evidence") || "",
    };

    const result = await addSkill(skillData);

    if (result.error) {
      alert(`⚠️ ${result.error}`);
      return;
    }

    alert("✅ Skill added successfully!");
    // Clear and restore placeholders safely
addSkillForm.reset();

// Force placeholder visibility (Safari/Chrome autofill fix)
setTimeout(() => {
  const skillName = document.getElementById("skillName");
  const proficiency = document.getElementById("proficiency");
  const evidence = document.getElementById("evidence");

  skillName.value = "";
  proficiency.value = "";
  evidence.value = "";

  // Manually trigger re-render of placeholder
  skillName.dispatchEvent(new Event("input"));
  proficiency.dispatchEvent(new Event("input"));
  evidence.dispatchEvent(new Event("input"));
}, 50);

await render();

  /** Utility */
  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  // Initial render
  render();
})();