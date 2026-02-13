async function apiGetSubjects(){
  const res = await fetch("/api/subjects");
  return await res.json();
}

async function apiAddSubject(payload){
  const res = await fetch("/api/subjects", {
    method:"POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify(payload)
  });
  return await res.json();
}

async function apiUpdateSubject(id, units_completed){
  const res = await fetch(`/api/subjects/${id}`, {
    method:"PATCH",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({units_completed})
  });
  return await res.json();
}

async function apiDeleteSubject(id){
  const res = await fetch(`/api/subjects/${id}`, { method:"DELETE" });
  return await res.json();
}

function percent(done, total){
  if(!total) return 0;
  return Math.round((done/total)*100);
}

async function renderSubjects(){
  const box = document.getElementById("subjectsList");
  if(!box) return;

  const data = await apiGetSubjects();
  const subjects = data.subjects || [];

  if(subjects.length === 0){
    box.innerHTML = `<div class="item small">No subjects yet. Add your first subject.</div>`;
    return;
  }

  box.innerHTML = subjects.map(s=>{
    const p = percent(s.units_completed, s.total_units);
    return `
      <div class="item">
        <div style="display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap">
          <div>
            <b>${escapeHtml(s.name)}</b>
            <div class="small">Exam: ${escapeHtml(s.exam_date)} • Difficulty: ${escapeHtml(s.difficulty)}</div>
            <div class="small">Units: ${s.units_completed}/${s.total_units} (${p}%)</div>
          </div>

          <div class="top-actions">
            <input type="number" min="0" max="${s.total_units}" value="${s.units_completed}"
              style="width:110px"
              onchange="updateUnits(${s.id}, this.value)">
            <button class="btn danger" onclick="deleteSubject(${s.id})">Delete</button>
          </div>
        </div>

        <div class="progressbar"><div style="width:${p}%"></div></div>
      </div>
    `;
  }).join("");
}

function escapeHtml(str){
  return String(str || "").replaceAll("&","&amp;")
    .replaceAll("<","&lt;").replaceAll(">","&gt;")
    .replaceAll('"',"&quot;").replaceAll("'","&#039;");
}

window.updateUnits = async function(id, v){
  await apiUpdateSubject(id, v);
  await renderSubjects();
}

window.deleteSubject = async function(id){
  await apiDeleteSubject(id);
  await renderSubjects();
}

window.addSubjectFromForm = async function(){
  const name = document.getElementById("subName").value.trim();
  const exam_date = document.getElementById("examDate").value;
  const total_units = document.getElementById("totalUnits").value;
  const difficulty = document.getElementById("difficulty").value;

  const msg = document.getElementById("msg");
  msg.innerHTML = "";

  const out = await apiAddSubject({name, exam_date, total_units, difficulty});
  if(out.error){
    msg.innerHTML = `<div class="error">${out.error}</div>`;
    return;
  }

  document.getElementById("subName").value = "";
  document.getElementById("examDate").value = "";
  document.getElementById("totalUnits").value = "5";
  document.getElementById("difficulty").value = "Medium";

  await renderSubjects();
}

document.addEventListener("DOMContentLoaded", renderSubjects);