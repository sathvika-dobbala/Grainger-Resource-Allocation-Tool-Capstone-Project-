
    const projectId = new URLSearchParams(window.location.search).get("projectID");
    const nameEl = document.getElementById("projName");
    const membersEl = document.getElementById("members");
    const skillsEl = document.getElementById("skills");

    async function init() {
      const res = await fetch(`/api/projects`);
    const data = await res.json();
    if (!data.success) return alert("Failed to load project");

      const project = data.projects.find((p) => p.projectID == projectId);
    if (!project) return alert("Project not found");

    nameEl.textContent = project.projectName;
    document.getElementById("status").value = project.status || "Not Started";
    document.getElementById("startDate").value = project.startDate || "";
    document.getElementById("endDate").value = project.endDate || "";
    document.getElementById("priority").value = project.priority || "Medium";

    // Render Team Members
    membersEl.innerHTML = (project.members || [])
        .map((m) => {
          const initials = m.fullName
    ? m.fullName
    .split(" ")
                .map((n) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2)
    : "NA";
    const photo = m.photo || "";
    const avatarHTML = photo
    ? `<div class="avatar"><img src="${photo}" alt="${m.fullName}"></div>`
    : `<div class="avatar">${initials}</div>`;
    return `
    <div class="member-card">
        <div class="member-info">
            ${avatarHTML}
            <div class="member-text">
                <a href="./employee-dashboard.html?empID=${m.empID}">
                    ${m.fullName}
                </a>
                <span class="emp-id">ID: ${m.empID || "—"}</span>
            </div>
        </div>
        <div class="member-role">${m.role || "Contributor"}</div>
    </div>
    `;
        })
    .join("");

    // Skills Section
    try {
        const skillRes = await fetch(`/api/projects/${projectId}/skills`);
    const skillData = await skillRes.json();
    skillsEl.innerHTML =
    (skillData.skills || [])
            .map((s) => `<span class="skill-tag">${s.skillName}</span>`)
    .join("") || "<span class='muted'>No skills saved</span>";
      } catch {
        skillsEl.innerHTML = "<span class='muted'>No skills saved</span>";
      }
    }

    async function saveDetails() {
      const payload = {
        status: document.getElementById("status").value,
    priority: document.getElementById("priority").value,
    startDate: document.getElementById("startDate").value,
    endDate: document.getElementById("endDate").value,
      };
    const res = await fetch(`/api/projects/${projectId}`, {
        method: "PUT",
    headers: {"Content-Type": "application/json" },
    body: JSON.stringify(payload),
      });
    const data = await res.json();
    alert(data.message || data.error);
    }

    async function addMember() {
      const nameOrID = prompt("Enter employee ID or name to add:");
    if (!nameOrID) return;
    const role = prompt("Enter role (Lead/Contributor):", "Contributor");
    const res = await fetch(`/api/projects/${projectId}/members`, {
        method: "POST",
    headers: {"Content-Type": "application/json" },
    body: JSON.stringify({nameOrID, role}),
      });
    const data = await res.json();
    alert(data.message || data.error);
    if (data.success) init();
    }

    async function editMember() {
      const nameOrID = prompt("Enter employee ID or name to edit:");
    if (!nameOrID) return;
    const newRole = prompt("Enter new role (Lead/Contributor):");
    const res = await fetch(`/api/projects/${projectId}/members/${nameOrID}`, {
        method: "PUT",
    headers: {"Content-Type": "application/json" },
    body: JSON.stringify({role: newRole }),
      });
    const data = await res.json();
    alert(data.message || data.error);
    if (data.success) init();
    }

    async function deleteMember() {
      const nameOrID = prompt("Enter employee ID or name to remove:");
    if (!nameOrID) return;
    if (!confirm("Are you sure you want to remove this member?")) return;
    const res = await fetch(`/api/projects/${projectId}/members/${nameOrID}`, {
        method: "DELETE",
      });
    const data = await res.json();
    alert(data.message || data.error);
    if (data.success) init();
    }

    async function deleteProject() {
  if (!confirm("⚠️ Are you sure you want to permanently delete this project? This action cannot be undone.")) return;

    try {
    const res = await fetch(`/api/projects/${projectId}`, {
        method: "DELETE",
    });

    const data = await res.json();

    if (data.success) {
        alert("✅ Project deleted successfully.");
    window.location.href = "./projects-list.html";
    } else {
        alert("❌ Failed to delete project: " + (data.error || "Unknown error"));
    }
  } catch (err) {
        alert("⚠️ Error deleting project: " + err.message);
  }
}

    init();
