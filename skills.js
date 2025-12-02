let managerID = null;
let categories = [];      // cache categories
let allSkills = [];       // full unfiltered dataset

// -------------------------------------------
// Load logged-in manager
// -------------------------------------------
async function loadManagerInfo() {
    const res = await fetch("/api/me");
    const data = await res.json();

    if (!data.success) {
        window.location.href = "./login.html";
        return;
    }

    managerID = data.manager_id;

    document.getElementById("managerName").textContent = "Welcome, " + data.manager_name;
    document.getElementById("managerDepartment").textContent = data.department_name;
    document.getElementById("managerEmail").textContent = data.manager_email;

    await loadCategories();
    await loadSkills();
}
loadManagerInfo();

// -------------------------------------------
// Logout
// -------------------------------------------
function logout() {
    fetch("/api/logout", { method: "POST" }).finally(() => {
        window.location.href = "./login.html";
    });
}

// -------------------------------------------
// Load skill categories
// -------------------------------------------
async function loadCategories() {
    const res = await fetch("/api/skill-categories");
    const data = await res.json();

    categories = data.categories;   // store in memory

    const select = document.getElementById("newSkillCategory");
    select.innerHTML = "";

    categories.forEach(c => {
        const opt = document.createElement("option");
        opt.value = c.skillCategoryID;
        opt.textContent = c.skillCategoryName;
        select.appendChild(opt);
    });
}

// -------------------------------------------
// Load all manager skills
// -------------------------------------------
async function loadSkills() {
    const res = await fetch(`/api/manager/${managerID}/skills`);
    const data = await res.json();

    allSkills = data.skills;  // save full dataset

    renderSkillTable(allSkills);
}

// -------------------------------------------
// Render table from a given list
// -------------------------------------------
function renderSkillTable(skillList) {
    const tbody = document.getElementById("skillTableBody");
    tbody.innerHTML = "";

    skillList.forEach(skill => {
        const row = document.createElement("tr");

        row.innerHTML = `
            <td>
                <input value="${skill.skillName}" id="name-${skill.skillID}">
            </td>
            <td>
                <select id="cat-${skill.skillID}">
                    ${buildCategoryOptions(skill.skillCategoryID)}
                </select>
            </td>
            <td>
                <div class="row-actions">
                    <button onclick="updateSkill(${skill.skillID})">Update</button>
                    <button class="danger" onclick="deleteSkill(${skill.skillID})">Delete</button>
                </div>
            </td>
        `;

        tbody.appendChild(row);
    });
}

// -------------------------------------------
// Build category dropdown
// -------------------------------------------
function buildCategoryOptions(selectedID) {
    let html = "";
    categories.forEach(c => {
        html += `
            <option value="${c.skillCategoryID}"
                ${c.skillCategoryID == selectedID ? "selected" : ""}>
                ${c.skillCategoryName}
            </option>`;
    });
    return html;
}

// -------------------------------------------
// Add new skill (with duplicate popup)
// -------------------------------------------
async function addSkill() {
    const name = document.getElementById("newSkillName").value.trim();
    const cat = document.getElementById("newSkillCategory").value;

    if (!name) return alert("Skill name is required");

    const res = await fetch(`/api/manager/${managerID}/skills`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
            skillName: name,
            skillCategoryID: cat
        })
    });

    const data = await res.json();

    if (!res.ok) {
        alert(data.error || "Error adding skill");
        return;
    }

    alert("Skill added successfully!");

    document.getElementById("newSkillName").value = "";
    loadSkills();
}

// -------------------------------------------
// Update skill (with duplicate popup)
// -------------------------------------------
async function updateSkill(skillID) {
    const name = document.getElementById(`name-${skillID}`).value.trim();
    const cat = document.getElementById(`cat-${skillID}`).value;

    const res = await fetch(`/api/manager/${managerID}/skills/${skillID}`, {
        method: "PUT",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({
            skillName: name,
            skillCategoryID: cat
        })
    });

    const data = await res.json();

    if (!res.ok) {
        alert(data.error || "Error updating skill");
        return;
    }

    alert("Skill updated successfully!");

    loadSkills();
}

// -------------------------------------------
// Delete skill
// -------------------------------------------
async function deleteSkill(skillID) {
    if (!confirm("Delete this skill?")) return;

    await fetch(`/api/manager/${managerID}/skills/${skillID}`, { method: "DELETE" });

    loadSkills();
}

// -------------------------------------------
// SEARCH — by name OR category
// -------------------------------------------
function filterSkills() {
    const q = document.getElementById("searchInput").value.toLowerCase();

    const filtered = allSkills.filter(s => {
        const nameMatch = s.skillName.toLowerCase().includes(q);

        const catName = categories.find(c => c.skillCategoryID == s.skillCategoryID)?.skillCategoryName || "";
        const catMatch = catName.toLowerCase().includes(q);

        return nameMatch || catMatch;
    });

    renderSkillTable(filtered);
}

function clearSearch() {
    document.getElementById("searchInput").value = "";
    renderSkillTable(allSkills);
}
