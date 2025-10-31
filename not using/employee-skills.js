(function () {
  "use strict";

  let employeeId = null;
  let employeeData = null;
  let skillsData = [];
  let allSkills = [];
  let projectsData = [];

  // -----------------------------
  // URL Parameter & Navigation
  // -----------------------------
  const urlParams = new URLSearchParams(window.location.search);
  employeeId = urlParams.get("id");

  if (!employeeId) {
    alert("No employee ID provided");
    window.location.href = "./manager-portal.html";
    return;
  }

  document.getElementById("editProfileBtn").addEventListener("click", () => {
    window.location.href = `./employee.html?id=${employeeId}`;
  });

  // -----------------------------
  // API Fetch Functions
  // -----------------------------
  async function fetchEmployee() {
    const res = await fetch(`/employees/${employeeId}`);
    return await res.json();
  }

  async function fetchEmployeeSkills() {
    const res = await fetch(`/employees/${employeeId}/skills`);
    const data = await res.json();
    return data.skills || [];
  }

  async function fetchAllSkills() {
    const res = await fetch("/skills");
    return await res.json();
  }

  async function fetchEmployeeProjects() {
    const res = await fetch(`/employees/${employeeId}/projects`);
    return await res.json();
  }

  async function saveEmployeeSkills(skills) {
    const res = await fetch(`/employees/${employeeId}/skills`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ skills }),
    });
    return await res.json();
  }

  // -----------------------------
  // Rendering Functions
  // -----------------------------
  function renderEmployeeHeader() {
    const avatarDiv = document.getElementById("employeeAvatar");
    if (employeeData.photo) {
      avatarDiv.innerHTML = `<img src="${employeeData.photo}" class="avatar-large" alt="${employeeData.fullName}">`;
    } else {
      const initials = (employeeData.fullName || "?")
        .split(/\s+/)
        .map((s) => s[0])
        .filter(Boolean)
        .slice(0, 2)
        .join("")
        .toUpperCase();
      avatarDiv.innerHTML = `<div class="avatar-placeholder-large">${initials}</div>`;
    }

    document.getElementById("employeeName").textContent =
      employeeData.fullName || "Unknown";
    document.getElementById("employeeTitle").textContent =
      employeeData.title || "No title";
    document.getElementById("employeeDepartment").textContent =
      employeeData.departmentname || "No department";
    document.getElementById("employeeEmail").textContent =
      employeeData.email || "No email";
  }

  function renderStats() {
    document.getElementById("totalSkills").textContent = skillsData.length;
    document.getElementById("activeProjects").textContent = projectsData.filter(
      (p) => p.status === "In Progress"
    ).length;

    const avgProf =
      skillsData.length > 0
        ? (
            skillsData.reduce(
              (sum, s) => sum + (s.profiencylevel || 0),
              0
            ) / skillsData.length
          ).toFixed(1)
        : "0";
    document.getElementById("avgProficiency").textContent = avgProf;

    let totalDays = 0;
    projectsData.forEach((proj) => {
      if (proj.startDate) {
        const start = new Date(proj.startDate);
        const end = proj.endDate ? new Date(proj.endDate) : new Date();
        const days = Math.floor((end - start) / (1000 * 60 * 60 * 24));
        totalDays += Math.max(0, days);
      }
    });
    document.getElementById("projectTime").textContent = `${totalDays}d`;
  }

  function renderSkills() {
  const container = document.getElementById("skillsList");

  if (skillsData.length === 0) {
    container.innerHTML =
      '<div class="empty-state">No skills recorded yet. Add skills to track proficiency.</div>';
    return;
  }

  // ✅ render without pre-populating all options
  container.innerHTML = skillsData
    .map(
      (skill, index) => `
      <div class="skill-row" data-index="${index}">
        <div>
          <select class="skill-name" data-index="${index}">
            <option value="${skill.skillID}" selected>${skill.skillName}</option>
          </select>
          <div class="category">${
            skill.skillCategoryname || "Uncategorized"
          }</div>
        </div>
        <select class="proficiency-level" data-index="${index}">
          ${[1, 2, 3, 4, 5]
            .map(
              (lvl) =>
                `<option value="${lvl}" ${
                  skill.profiencylevel === lvl ? "selected" : ""
                }>${lvl} - ${
                  ["Beginner", "Novice", "Intermediate", "Advanced", "Expert"][
                    lvl - 1
                  ]
                }</option>`
            )
            .join("")}
        </select>
        <input type="text" class="evidence" data-index="${index}" placeholder="Evidence" value="${
        skill.evidence || ""
      }">
        <button class="remove-skill" data-index="${index}">Remove</button>
      </div>
    `
    )
    .join("");

  // ✅ Initialize Select2 after rendering (live search only)
  $(".skill-name")
    .select2("destroy")
    .select2({
      placeholder: "Type to search or add a skill...",
      tags: true,                // allow adding new skills
      minimumInputLength: 2,     // only show results after typing 2 letters
      width: "100%",
      ajax: {
        url: "/skills",
        dataType: "json",
        delay: 250,
        data: function (params) {
          return { q: params.term };
        },
        processResults: function (data, params) {
          const searchTerm = params.term?.toLowerCase() || "";
          const filtered = data.filter((s) =>
            s.skillName.toLowerCase().includes(searchTerm)
          );
          return {
            results: filtered.map((s) => ({
              id: s.skillID,
              text: s.skillName,
            })),
          };
        },
      },
      createTag: function (params) {
        const term = $.trim(params.term);
        if (term === "") return null;
        return { id: term, text: term, newOption: true };
      },
      templateResult: function (data) {
        if (data.loading) return "Searching...";
        const label = data.newOption ? " (new skill)" : "";
        return `${data.text}${label}`;
      },
      templateSelection: function (data) {
        return data.text || data.id;
      },
    });

  // ✅ event bindings (same)
  container.querySelectorAll(".remove-skill").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      const index = parseInt(e.target.dataset.index);
      skillsData.splice(index, 1);
      renderSkills();
      renderStats();
    });
  });

  container.querySelectorAll(".proficiency-level").forEach((select) => {
    select.addEventListener("change", (e) => {
      const index = parseInt(e.target.dataset.index);
      skillsData[index].profiencylevel = parseInt(e.target.value);
      renderStats();
    });
  });

  container.querySelectorAll(".evidence").forEach((input) => {
    input.addEventListener("input", (e) => {
      const index = parseInt(e.target.dataset.index);
      skillsData[index].evidence = e.target.value;
    });
  });
}


    // Event Listeners
    container.querySelectorAll(".remove-skill").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        const index = parseInt(e.target.dataset.index);
        skillsData.splice(index, 1);
        renderSkills();
        renderStats();
      });
    });

    container.querySelectorAll(".proficiency-level").forEach((select) => {
      select.addEventListener("change", (e) => {
        const index = parseInt(e.target.dataset.index);
        skillsData[index].profiencylevel = parseInt(e.target.value);
        renderStats();
      });
    });

    container.querySelectorAll(".evidence").forEach((input) => {
      input.addEventListener("input", (e) => {
        const index = parseInt(e.target.dataset.index);
        skillsData[index].evidence = e.target.value;
      });
    });
  }

  function renderProjects() {
    const container = document.getElementById("projectsList");
    if (projectsData.length === 0) {
      container.innerHTML =
        '<div class="empty-state">No projects assigned yet.</div>';
      return;
    }

    container.innerHTML = projectsData
      .map((proj) => {
        const statusClass = proj.status.toLowerCase().replace(/\s+/g, "-");
        const startDate = proj.startDate
          ? new Date(proj.startDate).toLocaleDateString()
          : "N/A";
        const endDate = proj.endDate
          ? new Date(proj.endDate).toLocaleDateString()
          : "Ongoing";
        return `
          <div class="project-card">
            <div class="project-name">${proj.projectName}</div>
            <div class="project-meta">
              <span class="badge ${statusClass}">${proj.status}</span>
              <span>Role: ${proj.role || "N/A"}</span>
              <span>Start: ${startDate}</span>
              <span>End: ${endDate}</span>
            </div>
          </div>
        `;
      })
      .join("");
  }

  // -----------------------------
  // Event Listeners
  // -----------------------------
  document.getElementById("addSkillBtn").addEventListener("click", () => {
    const selected = $("#skillSelect").select2("data")[0];

    if (!selected) {
      alert("Please select or type a skill to add.");
      return;
    }

    const existing = skillsData.find(
      (s) => s.skillName.toLowerCase() === selected.text.toLowerCase()
    );
    if (existing) {
      alert("This skill is already added.");
      return;
    }

    const foundSkill = allSkills.find((s) => s.skillName === selected.text);
    const skillID = foundSkill ? foundSkill.skillID : null;
    const skillCategory = foundSkill
      ? foundSkill.skillCategoryname
      : "Uncategorized";

    skillsData.push({
      skillID: skillID,
      skillName: selected.text,
      skillCategoryname: skillCategory,
      profiencylevel: 1,
      evidence: "",
    });

    renderSkills();
    renderStats();
    $("#skillSelect").val(null).trigger("change");
  });

  document.getElementById("saveBtn").addEventListener("click", async () => {
    try {
      await saveEmployeeSkills(skillsData);
      alert("✅ Skills updated successfully!");
      window.location.reload();
    } catch (error) {
      alert("❌ Error saving skills: " + error.message);
    }
  });

  // -----------------------------
  // Initialization
  // -----------------------------
  async function init() {
    try {
      employeeData = await fetchEmployee();
      skillsData = await fetchEmployeeSkills();
      allSkills = await fetchAllSkills();
      projectsData = await fetchEmployeeProjects();

      renderEmployeeHeader();
      renderStats();
      renderSkills();
      renderProjects();
    } catch (error) {
      console.error("Error initializing dashboard:", error);
      alert("Error loading employee data");
    }
  }

  init();
})();
