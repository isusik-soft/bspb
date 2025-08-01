function addOperationRow() {
  const tbody = document.querySelector('#opsTable tbody');
  const tr = document.createElement('tr');
  tr.innerHTML = `
    <td><input type="date" class="form-control" required></td>
    <td><input type="text" class="form-control" placeholder="Контрагент"></td>
    <td><input type="text" class="form-control" placeholder="Описание" required></td>
    <td><input type="number" step="0.01" class="form-control" placeholder="0.00" required></td>
    <td><button type="button" class="btn btn-outline-danger btn-sm remove-op">×</button></td>
  `;
  tbody.appendChild(tr);
}

document.getElementById('addOp').addEventListener('click', addOperationRow);

document.getElementById('opsTable').addEventListener('click', function(e) {
  if (e.target.classList.contains('remove-op')) {
    e.target.closest('tr').remove();
  }
});

addOperationRow();

document.getElementById('statementForm').addEventListener('submit', async function(e) {
  e.preventDefault();
  const ops = [];
  document.querySelectorAll('#opsTable tbody tr').forEach(row => {
    const inputs = row.querySelectorAll('input');
    const [date, counterparty, desc, amount] = inputs;
    if (date.value && desc.value && amount.value) {
      ops.push({
        date: date.value,
        counterparty: counterparty.value,
        description: desc.value,
        amount: parseFloat(amount.value)
      });
    }
  });
  const payload = {
    fio: document.getElementById('fio').value,
    account: document.getElementById('account').value,
    from: document.getElementById('start').value,
    to: document.getElementById('end').value,
    operations: ops
  };
  const resp = await fetch('/statement/custom', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  if (!resp.ok) {
    alert('Ошибка при генерации выписки');
    return;
  }
  const blob = await resp.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'statement.pdf';
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
});
