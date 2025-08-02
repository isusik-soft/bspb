(function () {
  const dashboard = document.getElementById('dashboard');
  const editor = document.getElementById('editor');
  const statementsBody = document.querySelector('#statementsTable tbody');
  const newBtn = document.getElementById('newStatementBtn');
  const backBtn = document.getElementById('backToDashboard');
  const addOpBtn = document.getElementById('addOperation');
  const saveBtn = document.getElementById('saveDraft');
  const pdfBtn = document.getElementById('generatePdf');
  const saveStatus = document.getElementById('saveStatus');

  const accountInput = document.getElementById('accountInput');
  const ownerInput = document.getElementById('ownerInput');
  const startInput = document.getElementById('periodStart');
  const endInput = document.getElementById('periodEnd');
  const openingInput = document.getElementById('openingBalance');
  const incomingEl = document.getElementById('totalIncoming');
  const outgoingEl = document.getElementById('totalOutgoing');
  const closingEl = document.getElementById('closingBalance');
  const opsBody = document.querySelector('#operationsTable tbody');
  const searchInput = document.getElementById('searchInput');

  let saveTimeout = null;

  function showDashboard() {
    editor.classList.add('d-none');
    dashboard.classList.remove('d-none');
    refreshStatements();
  }

  function showEditor() {
    dashboard.classList.add('d-none');
    editor.classList.remove('d-none');
    loadDraft();
    updateTotals();
  }

  newBtn.addEventListener('click', showEditor);
  backBtn.addEventListener('click', showDashboard);

  searchInput.addEventListener('input', () => {
    const q = searchInput.value.toLowerCase();
    Array.from(statementsBody.querySelectorAll('tr')).forEach(tr => {
      tr.style.display = tr.textContent.toLowerCase().includes(q) ? '' : 'none';
    });
  });

  function refreshStatements() {
    fetch('/statements').then(r => r.ok ? r.json() : []).then(data => {
      statementsBody.innerHTML = '';
      data.forEach(st => {
        const tr = document.createElement('tr');
        const period = `${st.period_start} - ${st.period_end}`;
        const created = new Date(st.generated_at).toLocaleString('ru-RU');
        tr.innerHTML =
          `<td>${st.id}</td>` +
          `<td>${st.account_number}</td>` +
          `<td>${st.owner || ''}</td>` +
          `<td>${period}</td>` +
          `<td>${st.status || 'сгенерирована'}</td>` +
          `<td>${created}</td>` +
          `<td><a class="btn btn-sm btn-outline-secondary" href="/statement/${st.id}.pdf" target="_blank">PDF</a></td>`;
        statementsBody.appendChild(tr);
      });
    });
  }

  function addOperation(op = {}) {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><input type="date" class="form-control form-control-sm op-date" value="${op.date || ''}"></td>
      <td><input type="text" class="form-control form-control-sm op-counterparty" value="${op.counterparty || ''}"></td>
      <td><input type="text" class="form-control form-control-sm op-description" value="${op.description || ''}"></td>
      <td><input type="number" step="0.01" class="form-control form-control-sm op-amount" value="${op.amount != null ? op.amount : ''}"></td>
      <td class="text-nowrap">
        <button class="btn btn-sm btn-outline-secondary duplicate" title="Дублировать">⧉</button>
        <button class="btn btn-sm btn-outline-danger delete" title="Удалить">✕</button>
      </td>`;
    opsBody.appendChild(tr);

    const inputs = tr.querySelectorAll('input');
    inputs.forEach(inp => inp.addEventListener('input', updateTotalsAndSave));

    tr.querySelector('.delete').addEventListener('click', () => {
      tr.remove();
      updateTotalsAndSave();
    });
    tr.querySelector('.duplicate').addEventListener('click', () => {
      const data = getRowData(tr);
      addOperation(data);
      updateTotalsAndSave();
    });
  }

  function getNumber(input) {
    const val = input.valueAsNumber;
    return Number.isNaN(val) ? 0 : val;
  }

  function getRowData(tr) {
    return {
      date: tr.querySelector('.op-date').value,
      counterparty: tr.querySelector('.op-counterparty').value,
      description: tr.querySelector('.op-description').value,
      amount: getNumber(tr.querySelector('.op-amount'))
    };
  }

  function gatherData() {
    const operations = Array.from(opsBody.querySelectorAll('tr')).map(tr => getRowData(tr));
    return {
      account: accountInput.value.trim(),
      fio: ownerInput.value.trim(),
      from: startInput.value,
      to: endInput.value,
      opening_balance: getNumber(openingInput),
      operations
    };
  }

  function updateTotals() {
    let incoming = 0, outgoing = 0;
    Array.from(opsBody.querySelectorAll('tr')).forEach(tr => {
      const val = getNumber(tr.querySelector('.op-amount'));
      if (val >= 0) incoming += val; else outgoing += Math.abs(val);
    });
    const opening = getNumber(openingInput);
    const closing = opening + incoming - outgoing;
    incomingEl.textContent = incoming.toFixed(2);
    outgoingEl.textContent = outgoing.toFixed(2);
    closingEl.textContent = closing.toFixed(2);
  }

  function updateTotalsAndSave() {
    updateTotals();
    saveDraftDebounced();
  }

  openingInput.addEventListener('input', updateTotalsAndSave);
  accountInput.addEventListener('input', saveDraftDebounced);
  ownerInput.addEventListener('input', saveDraftDebounced);
  startInput.addEventListener('input', saveDraftDebounced);
  endInput.addEventListener('input', saveDraftDebounced);

  addOpBtn.addEventListener('click', () => {
    addOperation();
    saveDraftDebounced();
  });

  function saveDraft() {
    const data = gatherData();
    localStorage.setItem('statementDraft', JSON.stringify(data));
    saveStatus.textContent = 'Сохранено';
  }

  function saveDraftDebounced() {
    saveStatus.textContent = 'Сохранение...';
    clearTimeout(saveTimeout);
    saveTimeout = setTimeout(saveDraft, 1500);
  }

  saveBtn.addEventListener('click', saveDraft);

  function loadDraft() {
    const raw = localStorage.getItem('statementDraft');
    opsBody.innerHTML = '';
    if (raw) {
      try {
        const data = JSON.parse(raw);
        accountInput.value = data.account || '';
        ownerInput.value = data.fio || '';
        startInput.value = data.from || '';
        endInput.value = data.to || '';
        openingInput.value = data.opening_balance != null ? data.opening_balance : 0;
        (data.operations || []).forEach(addOperation);
      } catch (e) {
        addOperation();
      }
    } else {
      addOperation();
    }
    updateTotals();
    saveStatus.textContent = '';
  }

  pdfBtn.addEventListener('click', async () => {
    const data = gatherData();
    const payload = {
      fio: data.fio,
      account: data.account,
      from: data.from,
      to: data.to,
      opening_balance: data.opening_balance,
      operations: data.operations
    };
    const resp = await fetch('/statement/custom', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!resp.ok) {
      alert('Ошибка генерации');
      return;
    }
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'statement.pdf';
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  });

  refreshStatements();
})();

