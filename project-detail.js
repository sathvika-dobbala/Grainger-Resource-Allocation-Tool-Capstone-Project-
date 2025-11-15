const projectId = new URLSearchParams(window.location.search).get("projectID");
const nameEl = document.getElementById("projName");
const membersEl = document.getElementById("members");
const skillsEl = document.getElementById("skills");

async function init() {
  const res = await fetch(`/api/projects/${projectId}`);
  const data = await res.json();

  console.log("PROJECT API RESPONSE:", data); // ← helps debug

  if (!data.success) return alert("Failed to load project.");
  const project = data.project;

  // ---------------------------
  // Basic Info
  // ---------------------------
  nameEl.textContent = project.projectName;
  document.getElementById("status").value = project.status || "Not Started";
  document.getElementById("startDate").value = project.startDate || "";
  document.getElementById("endDate").value = project.endDate || "";


  document.getElementById("priority").textContent = project.priority || "—";
  // // Priority (READ ONLY in your UI)
  // const priorityBox = document.getElementById("priority");
  // priorityBox.textContent = project.priority || "—";

  // ---------------------------
  // Team Members Array
  // ---------------------------
  const members = data.members || data.teamMembers || [];

  if (!Array.isArray(members) || members.length === 0) {
    membersEl.innerHTML = `<div class="muted">No team members assigned</div>`;
  } else {
    membersEl.innerHTML = members
      .map((m) => {
        const initials = m.fullName
          .split(" ")
          .map((n) => n[0])
          .join("")
          .toUpperCase()
          .slice(0, 2);

        return `
          <div class="member-card">
            <div class="member-info">
              <div class="avatar">${initials}</div>
              <div class="member-text">
                <a href="./employee-dashboard.html?empID=${m.empID}">
                  ${m.fullName}
                </a>
                <span class="emp-id">ID: ${m.empID}</span>
              </div>
            </div>
            <div class="member-role">${m.role}</div>
          </div>
        `;
      })
      .join("");
  }

  // ---------------------------
  // Load Skills
  // ---------------------------
  try {
    const skillRes = await fetch(`/api/projects/${projectId}/skills`);
    const skillData = await skillRes.json();

    skillsEl.innerHTML =
      (skillData.skills || [])
        .map((s) => `<span class="skill-tag">${s.skillName}</span>`)
        .join("") || `<span class="muted">No skills saved</span>`;
  } catch {
    skillsEl.innerHTML = `<span class="muted">No skills saved</span>`;
  }
}

/* --------------------------
   SAVE PROJECT DETAILS
--------------------------- */
async function saveDetails() {
  const payload = {
    projectName: nameEl.textContent,
    status: document.getElementById("status").value,
    startDate: document.getElementById("startDate").value,
    endDate: document.getElementById("endDate").value
  };

  const res = await fetch(`/api/projects/${projectId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  const data = await res.json();
  alert(data.message || data.error);
  if (data.success) init();
}

/* --------------------------
   MEMBER ROUTES
--------------------------- */
async function addMember() {
  const empID = prompt("Enter employee ID to add:");
  if (!empID) return;

  const role = prompt("Enter role (Lead/Contributor):", "Contributor") || "Contributor";

  const res = await fetch(`/api/projects/${projectId}/members`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ empID: Number(empID), role })
  });

  const data = await res.json();
  alert(data.message || data.error);
  if (data.success) init();
}

async function editMember() {
  const empID = prompt("Enter employee ID to update role:");
  if (!empID) return;

  const newRole = prompt("Enter new role (Lead/Contributor):");
  if (!newRole) return;

  const res = await fetch(`/api/projects/${projectId}/members/${empID}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ role: newRole })
  });

  const data = await res.json();
  alert(data.message || data.error);
  if (data.success) init();
}

async function deleteMember() {
  const empID = prompt("Enter employee ID to remove:");
  if (!empID) return;

  if (!confirm("Are you sure you want to remove this member?")) return;

  const res = await fetch(`/api/projects/${projectId}/members/${empID}`, {
    method: "DELETE"
  });

  const data = await res.json();
  alert(data.message || data.error);
  if (data.success) init();
}

/* --------------------------
   DELETE PROJECT
--------------------------- */
async function deleteProject() {
  if (!confirm("⚠️ Permanently delete this project?")) return;

  const res = await fetch(`/api/projects/${projectId}`, { method: "DELETE" });
  const data = await res.json();

  if (data.success) {
    alert("Project deleted.");
    window.location.href = "./projects-list.html";
  } else {
    alert("Error: " + (data.error || "Unknown error"));
  }
}

init();
