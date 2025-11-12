(function () {
  "use strict";

  let employeeId = null;
  let employeeData = null;
  let skillsData = [];
  let allSkills = [];
  let projectsData = [];

  // Get employee ID from URL
  const urlParams = new URLSearchParams(window.location.search);
  employeeId = urlParams.get("id");

  if (!employeeId) {
    alert("No employee ID provided");
    window.location.href = "./manager-portal.html";
    return;
  }

  // Edit Profile button
  const editBtn = document.getElementById("editProfileBtn");
  if (editBtn) {
    editBtn.addEventListener("click", () => {
      window.location.href = `./employee.html?id=${employeeId}`;
    });
  }

  // Delete Employee button
  const deleteBtn = document.getElementById("deleteBtn");
  if (deleteBtn) {
    deleteBtn.addEventListener("click", async () => {
      const confirmDelete = confirm("Are you sure you want to delete this employee?");
      if (confirmDelete) {
        try {
          const res = await fetch(`/employees/${employeeId}`, {
            method: "DELETE",
          });
          if (!res.ok) {
            throw new Error("Failed to delete employee");
          }
          alert("✅ Employee deleted successfully!");
          window.location.href = "./manager-portal.html"; // Redirect back to the employee list
        } catch (err) {
          alert("❌ Error deleting employee: " + err.message);
        }
      }
    });
  }

  // -------------------------------
  // 📡 API Functions
  // -------------------------------
  async function fetchEmployee() {
    const res = await fetch(`/employees/${employeeId}`);
    if (!res.ok) throw new Error("Employee not found");
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

  // -------------------------------
  // 🎨 Render Functions
  // -------------------------------
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
      employeeData.fullName || employeeData.fullname || `${employeeData.firstname || ''} ${employeeData.lastname || ''}`.trim() || "Unknown";
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

  // ✅ Updated renderSkills (no select2 errors)
  function renderSkills() {
    const container = document.getElementById("skillsList");
    if (skillsData.length === 0) {
      container.innerHTML =
        '<div class="empty-state">No skills recorded yet. Add skills to track proficiency.</div>';
      return;
    }

    container.innerHTML = skillsData
      .map(
        (skill, index) => `
        <div class="skill-row" data-index="${index}">
            <div>
                <input 
  type="text" 
  class="skill-name" 
  data-index="${index}" 
  list="skills-list" 
  placeholder="Type a skill..." 
  value="${skill.skillName}">
                <div class="category">${skill.skillCategoryname || "Uncategorized"}</div>
            </div>
            <select class="proficiency-level" data-index="${index}">
  ${[...Array(11).keys()]
            .map(
              (lvl) => `
        <option value="${lvl}" ${skill.profiencylevel === lvl ? "selected" : ""
                }>${lvl} - ${getSkillLevelLabel(lvl)}</option>
      `
            )
            .join("")}
  </select>
            <input type="text" class="evidence" data-index="${index}" 
                placeholder="Evidence" value="${skill.evidence || ""}">
            <button class="remove-skill" data-index="${index}">Remove</button>
        </div>
      `
      )
      .join("");
      

function getSkillLevelLabel(level) {
  const labels = {
    0: "None",
    1: "Novice",
    2: "Beginner",
    3: "Developing",
    4: "Intermediate",
    5: "Advanced",
    6: "Proficient",
    7: "Highly Skilled",
    8: "Expert",
    9: "Master",
    10: "Guru",
  };
  return labels[level] || "";
}

    // Search-by-typing feature
    container.querySelectorAll(".skill-name").forEach((input) => {
      input.addEventListener("input", async (e) => {
        const term = e.target.value.trim().toLowerCase();
        if (term.length < 1) return;

        const res = await fetch(`/skills?q=${encodeURIComponent(term)}`);
        const skills = await res.json();

        const dataList = document.getElementById("skills-list");
        dataList.innerHTML = skills
          .map((s) => `<option value="${s.skillName}"></option>`)
          .join("");
      });

      input.addEventListener("change", (e) => {
        const index = parseInt(e.target.dataset.index);
        const skill = allSkills.find(
          (s) => s.skillName.toLowerCase() === e.target.value.toLowerCase()
        );
        if (skill) {
          skillsData[index].skillID = skill.skillID;
          skillsData[index].skillName = skill.skillName;
          skillsData[index].skillCategoryname =
            skill.skillCategoryname || "Uncategorized";
        } else {
          skillsData[index].skillID = null;
          skillsData[index].skillName = e.target.value;
          skillsData[index].skillCategoryname = "Custom";
        }
      });
    });

    // Remove skill
    container.querySelectorAll(".remove-skill").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        const index = parseInt(e.target.dataset.index);
        skillsData.splice(index, 1);
        renderSkills();
        renderStats();
      });
    });

    // Proficiency level change
    container.querySelectorAll(".proficiency-level").forEach((select) => {
      select.addEventListener("change", (e) => {
        const index = parseInt(e.target.dataset.index);
        skillsData[index].profiencylevel = parseInt(e.target.value);
        renderStats();
      });
    });

    // Evidence change
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

  // -------------------------------
  // ➕ Add Skill / Save Actions
  // -------------------------------
  // document.getElementById("addSkillBtn").addEventListener("click", () => {
  //   if (allSkills.length === 0) {
  //     alert("No skills available. Please add skills to the system first.");
  //     return;
  //   }

  //   skillsData.push({
  //     skillID: allSkills[0].skillID,
  //     skillName: allSkills[0].skillName,
  //     skillCategoryname: allSkills[0].skillCategoryname,
  //     profiencylevel: 0,
  //     evidence: "",
  //   });
  //   renderSkills();
  //   renderStats();
  // });
  document.getElementById("addSkillBtn").addEventListener("click", () => {
  // Add an empty new skill row with placeholder text
  skillsData.push({
    skillID: null,
    skillName: "",
    skillCategoryname: "Uncategorized",
    profiencylevel: 0,
    evidence: "",
  });

  renderSkills();
  renderStats();

  // Focus the newly added skill input automatically
  setTimeout(() => {
    const lastSkill = document.querySelector(".skill-row:last-child .skill-name");
    if (lastSkill) lastSkill.focus();
  }, 50);
});


  document.getElementById("saveBtn").addEventListener("click", async () => {
    try {
      await saveEmployeeSkills(skillsData);
      alert("✅ Skills updated successfully!");
      window.location.reload();
    } catch (error) {
      // alert("❌ Error saving skills: " + error.message);
        alert("❌ Error saving skills, please ensure all skill names are picked from the list.");
    }
  });

  // -------------------------------
  // 🚀 Initialize
  // -------------------------------
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
