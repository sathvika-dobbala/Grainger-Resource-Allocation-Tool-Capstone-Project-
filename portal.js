/* Manager Portal Employee CRUD using localStorage */
(function () {
    "use strict";

    /** DOM Elements */
    const employeeTableBody = document.getElementById('employeeTableBody');
    const emptyState = document.getElementById('emptyState');
    const employeeCount = document.getElementById('employeeCount');
    const searchInput = document.getElementById('searchInput');
    const resetBtn = document.getElementById('resetBtn');
    const newBtn = document.getElementById('newBtn');
    const exportBtn = document.getElementById('exportBtn');
    const importBtn = document.getElementById('importBtn');
    const importInput = document.getElementById('importInput');

    // List page has no form/modal elements

    /** Storage helpers */
    const STORAGE_KEY = 'employees';
    function loadEmployees() {
        try {
            const raw = localStorage.getItem(STORAGE_KEY);
            return raw ? JSON.parse(raw) : [];
        } catch (e) { return []; }
    }
    function saveEmployees(employees) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(employees));
    }

    /** State */
    let allEmployees = loadEmployees();
    let query = '';
    let selectedId = '';

    /** Rendering */
    function render() {
        const filtered = filterEmployees(allEmployees, query);
        employeeCount.textContent = `${filtered.length} ${filtered.length === 1 ? 'employee' : 'employees'}`;
        if (filtered.length === 0) {
            employeeTableBody.innerHTML = '';
            emptyState.hidden = false;
            return;
        }
        emptyState.hidden = true;
        const rows = filtered.map(toRowHtml).join('');
        employeeTableBody.innerHTML = rows;
        applySelectionHighlight();
    }

    function toRowHtml(emp) {
        const statusBadge = `<span class="badge">${escapeHtml(emp.status || '')}</span>`;
        const avatar = renderAvatar(emp);
        return `
            <tr data-id="${emp.id}">
                <td class="avatarCell">${avatar}</td>
                <td>${escapeHtml(emp.fullName || '')}</td>
                <td>${escapeHtml(emp.title || '')}</td>
                <td>${escapeHtml(emp.department || '')}</td>
                <td>${escapeHtml(emp.email || '')}</td>
                <td>${escapeHtml(emp.phone || '')}</td>
                <td>${statusBadge}</td>
                <td>
                    <button type="button" data-action="view">Open</button>
                </td>
            </tr>
        `;
    }

    function applySelectionHighlight() {
        const rows = employeeTableBody.querySelectorAll('tr');
        rows.forEach(r => {
            const id = r.getAttribute('data-id');
            if (id === selectedId) r.classList.add('selected'); else r.classList.remove('selected');
        });
    }

    function renderAvatar(emp) {
        const url = emp.photo;
        if (url) {
            return `<img alt="${escapeHtml(emp.fullName || 'Photo')}" src="${url}" class="avatar">`;
        }
        const initials = (emp.fullName || '?').split(/\s+/).map(s => s[0]).filter(Boolean).slice(0,2).join('').toUpperCase();
        return `<span class="avatarPlaceholder" aria-label="No photo">${escapeHtml(initials)}</span>`;
    }

    function filterEmployees(employees, q) {
        if (!q) return employees;
        const terms = q.toLowerCase().split(/\s+/).filter(Boolean);
        return employees.filter(e => {
            const hay = [e.fullName, e.title, e.department, e.email, e.phone, e.status, e.location]
                .map(v => (v || '').toLowerCase()).join(' ');
            return terms.every(t => hay.includes(t));
        });
    }

    /** Utilities */
    function escapeHtml(str) {
        return String(str).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
    }
    // No-op form helpers in list page
    function clearForm() {}
    function fillForm() {}

    /** CRUD Operations */
    function upsertEmployee(payload) {
        if (payload.id) {
            const idx = allEmployees.findIndex(e => e.id === payload.id);
            if (idx !== -1) {
                allEmployees[idx] = payload;
            } else {
                allEmployees.push(payload);
            }
        } else {
            payload.id = String(Date.now());
            allEmployees.push(payload);
        }
        saveEmployees(allEmployees);
        render();
    }
    function deleteEmployee(id) {
        allEmployees = allEmployees.filter(e => e.id !== id);
        saveEmployees(allEmployees);
        render();
    }

    /** CSV Export */
    function toCsvValue(value) {
        const s = value == null ? '' : String(value);
        if (/[",\n]/.test(s)) {
            return '"' + s.replaceAll('"', '""') + '"';
        }
        return s;
    }
    function employeesToCsv(employees) {
        const headers = ['id','fullName','title','department','email','phone','status','startDate','location','photo'];
        const lines = [headers.join(',')];
        for (const e of employees) {
            const row = [e.id,e.fullName,e.title,e.department,e.email,e.phone,e.status,e.startDate,e.location,e.photo]
                .map(toCsvValue)
                .join(',');
            lines.push(row);
        }
        return lines.join('\n');
    }
    function downloadCsv(filename, text) {
        const blob = new Blob([text], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }

    /** CSV Import */
    function parseCsv(text) {
        // Basic RFC4180-style parser supporting quotes and commas
        const rows = [];
        let current = '';
        let row = [];
        let inQuotes = false;
        for (let i = 0; i < text.length; i++) {
            const ch = text[i];
            if (inQuotes) {
                if (ch === '"') {
                    if (text[i + 1] === '"') { current += '"'; i++; }
                    else { inQuotes = false; }
                } else {
                    current += ch;
                }
            } else {
                if (ch === '"') { inQuotes = true; }
                else if (ch === ',') { row.push(current); current = ''; }
                else if (ch === '\n') { row.push(current); rows.push(row); row = []; current = ''; }
                else if (ch === '\r') { /* ignore CR */ }
                else { current += ch; }
            }
        }
        row.push(current);
        rows.push(row);
        return rows.filter(r => r.length > 1 || (r.length === 1 && r[0].trim() !== ''));
    }
    function importEmployeesFromCsv(text) {
        const rows = parseCsv(text);
        if (rows.length === 0) return { imported: 0, updated: 0 };
        const header = rows[0].map(h => h.trim());
        const expected = ['id','fullName','title','department','email','phone','status','startDate','location','photo'];
        // Allow case-insensitive header match and subset; require at least fullName
        const lowerHeader = header.map(h => h.toLowerCase());
        const indices = {};
        for (const key of expected) {
            indices[key] = lowerHeader.indexOf(key.toLowerCase());
        }
        if (indices.fullName === -1) {
            alert('CSV must include at least a fullName column.');
            return { imported: 0, updated: 0 };
        }
        let imported = 0, updated = 0;
        for (let r = 1; r < rows.length; r++) {
            const cols = rows[r];
            const record = {
                id: getCol(cols, indices.id),
                fullName: getCol(cols, indices.fullName),
                title: getCol(cols, indices.title),
                department: getCol(cols, indices.department),
                email: getCol(cols, indices.email),
                phone: getCol(cols, indices.phone),
                status: getCol(cols, indices.status) || 'Active',
                startDate: getCol(cols, indices.startDate),
                location: getCol(cols, indices.location),
                photo: getCol(cols, indices.photo)
            };
            if (!record.fullName) continue;
            if (record.id) {
                const idx = allEmployees.findIndex(e => e.id === record.id);
                if (idx !== -1) {
                    allEmployees[idx] = { ...allEmployees[idx], ...record };
                    updated++;
                } else {
                    allEmployees.push({ ...record });
                    imported++;
                }
            } else {
                record.id = String(Date.now() + r);
                allEmployees.push(record);
                imported++;
            }
        }
        saveEmployees(allEmployees);
        render();
        return { imported, updated };
    }
    function getCol(cols, idx) {
        return idx >= 0 && idx < cols.length ? cols[idx].trim() : '';
    }

    /** Event Listeners */
    searchInput.addEventListener('input', (e) => {
        query = e.target.value.trim();
        render();
    });
    resetBtn.addEventListener('click', () => {
        searchInput.value = '';
        query = '';
        render();
    });
    newBtn.addEventListener('click', () => {
        window.location.href = './employee.html';
    });
    exportBtn.addEventListener('click', () => {
        const csv = employeesToCsv(allEmployees);
        const date = new Date();
        const pad = (n) => String(n).padStart(2, '0');
        const ts = `${date.getFullYear()}${pad(date.getMonth()+1)}${pad(date.getDate())}_${pad(date.getHours())}${pad(date.getMinutes())}`;
        downloadCsv(`employees_${ts}.csv`, csv);
    });
    importBtn.addEventListener('click', () => {
        importInput.value = '';
        importInput.click();
    });
    importInput.addEventListener('change', async () => {
        const file = importInput.files && importInput.files[0];
        if (!file) return;
        const text = await file.text();
        const { imported, updated } = importEmployeesFromCsv(text);
        alert(`Import complete.\nImported: ${imported}\nUpdated: ${updated}`);
    });

    // Remove form-related handlers on list page

    employeeTableBody.addEventListener('click', (e) => {
        const target = e.target;
        if (!(target instanceof HTMLElement)) return;
        const tr = target.closest('tr');
        const id = tr && tr.getAttribute('data-id');
        if (!id) return;
        const action = target.getAttribute('data-action');
        // On list page, open detail view
        window.location.href = `./employee.html?id=${encodeURIComponent(id)}`;
        selectedId = id;
        applySelectionHighlight();
    });

    // Initial render
    render();
})();


