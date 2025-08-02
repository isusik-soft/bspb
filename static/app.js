async function fetchAccounts() {
  const resp = await fetch('/accounts');
  if (!resp.ok) return;
  const accounts = await resp.json();
  const select = document.getElementById('accountSelect');
  select.innerHTML = '';
  accounts.forEach(acc => {
    const option = document.createElement('option');
    option.value = acc.id;
    option.textContent = `${acc.number} (${acc.currency})`;
    select.appendChild(option);
  });
}

async function refreshStatements() {
  const resp = await fetch('/statements');
  if (!resp.ok) return;
  const statements = await resp.json();
  const list = document.getElementById('statementsList');
  list.innerHTML = '';
  statements.forEach(st => {
    const li = document.createElement('li');
    li.className = 'list-group-item';
    const link = document.createElement('a');
    link.href = `/statement/${st.id}.pdf`;
    link.textContent = `${st.account_number} | ${st.period_start} - ${st.period_end}`;
    li.appendChild(link);
    list.appendChild(li);
  });
}

document.getElementById('generateForm').addEventListener('submit', async function (e) {
  e.preventDefault();
  const payload = {
    account_id: parseInt(document.getElementById('accountSelect').value, 10),
    from: document.getElementById('dbStart').value,
    to: document.getElementById('dbEnd').value
  };
  const resp = await fetch('/statement/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  if (!resp.ok) {
    alert('Ошибка при генерации выписки');
    return;
  }
  const data = await resp.json();
  const linkDiv = document.getElementById('generatedLink');
  linkDiv.innerHTML = `<a href="/statement/${data.id}.pdf" target="_blank">Скачать PDF</a>`;
  refreshStatements();
});

fetchAccounts();
refreshStatements();

