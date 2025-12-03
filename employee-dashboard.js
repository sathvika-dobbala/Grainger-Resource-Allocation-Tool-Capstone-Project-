(function () {
  "use strict";

  let employeeId = null;
  let employeeData = null;
  let skillsData = [];
  let allSkills = [];
  let projectsData = [];

  // Get employee ID from URL (supports both ?empID=5 and ?id=5)
const urlParams = new URLSearchParams(window.location.search);
employeeId = urlParams.get("empID") || urlParams.get("id");

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
  // Get employee's department first
  const deptId = employeeData.department;
  
  // Fetch only skills for this department
  const res = await fetch(`/skills?department=${deptId}`);
  const skills = await res.json();
  
  // Populate the datalist for dropdown
  const dataList = document.getElementById("skills-list");
  dataList.innerHTML = skills
    .map((s) => `<option value="${s.skillName}">${s.skillCategoryname || 'Uncategorized'}</option>`)
    .join("");
  
  return skills;
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
      document.getElementById("employeeID").textContent = `Employee ID: ${employeeId}`;
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
    
    // Get department from employee data
    const deptId = employeeData.department;
    
    if (term.length < 1) {
      // Show all department skills when empty
      const res = await fetch(`/skills?department=${deptId}`);
      const skills = await res.json();
      const dataList = document.getElementById("skills-list");
      dataList.innerHTML = skills
        .map((s) => `<option value="${s.skillName}"></option>`)
        .join("");
      return;
    }

    // Filter by search term within department
    const res = await fetch(`/skills?q=${encodeURIComponent(term)}&department=${deptId}`);
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

  // -------------------------------
// 📄 Resume Upload & Processing
// -------------------------------
const resumeUploadArea = document.getElementById("resumeUploadArea");
const resumeFile = document.getElementById("resumeFile");
const resumeFileName = document.getElementById("resumeFileName");
const processResumeBtn = document.getElementById("processResumeBtn");
const resumeStatus = document.getElementById("resumeStatus");

let selectedResumeFile = null;

// Click to upload
resumeUploadArea.addEventListener("click", () => resumeFile.click());

// File selection
resumeFile.addEventListener("change", (e) => {
  const file = e.target.files[0];
  if (file) {
    selectedResumeFile = file;
    resumeFileName.textContent = `📎 ${file.name}`;
    processResumeBtn.style.display = "block";
    resumeStatus.style.display = "none";
  }
});

// Process resume button
processResumeBtn.addEventListener("click", async () => {
  if (!selectedResumeFile) {
    showResumeStatus("error", "Please select a resume file first");
    return;
  }

  const formData = new FormData();
  formData.append("resume", selectedResumeFile);

  processResumeBtn.disabled = true;
  processResumeBtn.textContent = "🔄 Analyzing resume...";
  showResumeStatus("info", "Extracting skills from resume using AI...");

  try {
    const res = await fetch(`/employees/${employeeId}/upload-resume`, {
      method: "POST",
      body: formData,
    });

    const data = await res.json();

    if (!res.ok || !data.success) {
      throw new Error(data.error || "Failed to process resume");
    }

    // Merge new skills into existing skillsData
    const newSkills = data.skills || [];
    let addedCount = 0;
    let updatedCount = 0;

    for (const newSkill of newSkills) {
      const existingIndex = skillsData.findIndex(
        (s) => s.skillID === newSkill.skillID
      );

      if (existingIndex === -1) {
        // Add new skill
        skillsData.push({
          skillID: newSkill.skillID,
          skillName: newSkill.skillName,
          skillCategoryname: newSkill.categoryName || "Uncategorized",
          profiencylevel: newSkill.level || 3,
          evidence: newSkill.evidence || "Extracted from resume",
        });
        addedCount++;
      } else {
        // Update existing skill if new level is higher
        const existing = skillsData[existingIndex];
        if (newSkill.level > existing.profiencylevel) {
          existing.profiencylevel = newSkill.level;
          existing.evidence = `${existing.evidence || ""} | Resume: ${newSkill.evidence || ""}`.trim();
          updatedCount++;
        }
      }
    }

    showResumeStatus(
      "success",
      `✅ Success! Added ${addedCount} new skills, updated ${updatedCount} existing skills. Click "Save Changes" below to commit.`
    );

    // Re-render skills and stats
    renderSkills();
    renderStats();

    // Reset upload UI
    selectedResumeFile = null;
    resumeFile.value = "";
    resumeFileName.textContent = "";
    processResumeBtn.style.display = "none";
    processResumeBtn.textContent = "✨ Extract Skills from Resume";

  } catch (error) {
    console.error("Resume processing error:", error);
    showResumeStatus("error", `❌ Error: ${error.message}`);
  } finally {
    processResumeBtn.disabled = false;
    processResumeBtn.textContent = "✨ Extract Skills from Resume";
  }
});

function showResumeStatus(type, message) {
  resumeStatus.style.display = "block";
  resumeStatus.textContent = message;

  if (type === "success") {
    resumeStatus.style.background = "#dcfce7";
    resumeStatus.style.color = "#166534";
    resumeStatus.style.border = "1px solid #86efac";
  } else if (type === "error") {
    resumeStatus.style.background = "#fee2e2";
    resumeStatus.style.color = "#991b1b";
    resumeStatus.style.border = "1px solid #fca5a5";
  } else {
    resumeStatus.style.background = "#dbeafe";
    resumeStatus.style.color = "#1e40af";
    resumeStatus.style.border = "1px solid #93c5fd";
  }
}

  init();
})();
