let types = { enums: {} };
let libraryTemplates = { templates: [] };
let activeField = null;
const components = [];

function setActiveField(el) { activeField = el; }

function insertToken(token) {
  if (!activeField) { alert('Focus a text field first to insert this token.'); return; }
  activeField.value = token;
}

function renderTypesList() {
  const list = document.getElementById('types-list');
  list.innerHTML = '';
  const enums = types.enums || {};
  Object.keys(enums).sort().forEach(name => {
    const block = document.createElement('div'); block.className = 'enum-block';
    const h = document.createElement('h3'); h.textContent = name; block.appendChild(h);
    enums[name].forEach(tok => {
      const s = document.createElement('span'); s.className = 'token'; s.textContent = tok;
      s.addEventListener('click', () => insertToken(tok));
      block.appendChild(s);
    });
    list.appendChild(block);
  });
}

function createEnumSelect(enumName, selected) {
  const sel = document.createElement('select');
  const enums = types.enums || {};
  const arr = enums[enumName] || [];
  const empty = document.createElement('option'); empty.value = ''; empty.textContent = '--'; sel.appendChild(empty);
  arr.forEach(tok => {
    const o = document.createElement('option'); o.value = tok; o.textContent = tok;
    if (selected && selected === tok) o.selected = true;
    sel.appendChild(o);
  });
  return sel;
}

function renderTemplatePreview(preview, tmpl, form) {
  preview.innerHTML = '';
  // Pins
  const pins = Array.isArray(tmpl.pins) ? tmpl.pins : (Array.isArray(tmpl['pins']) ? tmpl['pins'] : []);
  if (pins.length) {
    const ph = document.createElement('h4'); ph.textContent = 'Pins (editable)'; preview.appendChild(ph);
    const pinContainer = document.createElement('div'); pinContainer.className = 'template-pins';
    pins.forEach((p, idx) => {
      const row = document.createElement('div'); row.className = 'template-pin-row';
      row.dataset.idx = idx;
      const num = document.createElement('input'); num.type='number'; num.value = p.number || p.physical_number || '';
      num.className = 'tpl-physical'; row.appendChild(labelWith('Physical', num));
      const name = document.createElement('input'); name.type='text'; name.value = p.name || ''; name.className='tpl-name'; row.appendChild(labelWith('Name', name));
      const group = document.createElement('input'); group.type='text'; group.value = p.group || p.name || ''; group.className='tpl-group'; row.appendChild(labelWith('Group', group));
      const roleText = document.createElement('input'); roleText.type='text'; roleText.value = p.role || ''; roleText.className='tpl-role-text';
      const roleSel = createEnumSelect('EEC_PinRole_t'); roleSel.className='tpl-role-select'; roleSel.addEventListener('change', ()=>{ if (roleSel.value) roleText.value = roleSel.value; });
      row.appendChild(labelWith('Role', roleText)); row.appendChild(roleSel);
      const elecText = document.createElement('input'); elecText.type='text'; elecText.value = p.electrical_requirement || p.electrical || ''; elecText.className='tpl-elec-text';
      const elecSel = createEnumSelect('EEC_SignalInterface_t'); elecSel.className='tpl-elec-select'; elecSel.addEventListener('change', ()=>{ if (elecSel.value) elecText.value = elecSel.value; });
      row.appendChild(labelWith('Electrical', elecText)); row.appendChild(elecSel);
      // supply
      const supText = document.createElement('input'); supText.type='text'; supText.value = (p.supply && (p.supply['enum'] || p.supply.enum)) || '' ; supText.className='tpl-supply';
      const volt = document.createElement('input'); volt.type='number'; volt.step='0.1'; volt.value = p.supply && p.supply.voltage_nominal ? p.supply.voltage_nominal : '' ; volt.className='tpl-voltage';
      const cur = document.createElement('input'); cur.type='number'; cur.step='0.01'; cur.value = p.supply && p.supply.current_max_a ? p.supply.current_max_a : '' ; cur.className='tpl-current';
      row.appendChild(labelWith('Supply token', supText)); row.appendChild(labelWith('Vnom', volt)); row.appendChild(labelWith('Imax', cur));
      // ground
      const gText = document.createElement('input'); gText.type='text'; gText.value = p.ground && p.ground.ground_class ? p.ground.ground_class : ''; gText.className='tpl-ground-text';
      const gSel = createEnumSelect('EEC_GroundClass_t'); gSel.className='tpl-ground-select'; gSel.addEventListener('change', ()=>{ if (gSel.value) gText.value = gSel.value; });
      row.appendChild(labelWith('Ground class', gText)); row.appendChild(gSel);
      pinContainer.appendChild(row);
    });
    preview.appendChild(pinContainer);
    const applyPins = document.createElement('button'); applyPins.textContent='Apply edited pins'; applyPins.addEventListener('click', ()=>{
      form._template_pins = collectPinsFromPreview(preview);
      alert('Applied '+ (form._template_pins ? form._template_pins.length : 0) + ' pins to device form.');
    });
    preview.appendChild(applyPins);
    // auto-apply
    form._template_pins = collectPinsFromPreview(preview);
  }
  // Signals
  const signals = Array.isArray(tmpl.signals) ? tmpl.signals : (Array.isArray(tmpl['signals']) ? tmpl['signals'] : []);
  if (signals.length) {
    const sh = document.createElement('h4'); sh.textContent = 'Signals (editable)'; preview.appendChild(sh);
    const sigContainer = document.createElement('div'); sigContainer.className = 'template-signals';
    signals.forEach((s, idx)=>{
      const srow = document.createElement('div'); srow.className='template-signal-row';
      srow.dataset.idx = idx;
      const prefix = document.createElement('input'); prefix.type='text'; prefix.value = s.prefix || ''; prefix.className='tpl-s-prefix'; srow.appendChild(labelWith('Prefix', prefix));
      const count = document.createElement('input'); count.type='number'; count.value = s.count || 1; count.className='tpl-s-count'; srow.appendChild(labelWith('Count', count));
      const iface = document.createElement('input'); iface.type='text'; iface.value = s.interface || s['interface'] || ''; iface.className='tpl-s-interface';
      const ifaceSel = createEnumSelect('EEC_SignalInterface_t'); ifaceSel.className='tpl-s-interface-select'; ifaceSel.addEventListener('change', ()=>{ if (ifaceSel.value) iface.value = ifaceSel.value; });
      srow.appendChild(labelWith('Interface', iface)); srow.appendChild(ifaceSel);
      const typ = document.createElement('input'); typ.type='text'; typ.value = s.type || s['type'] || ''; typ.className='tpl-s-type'; srow.appendChild(labelWith('Type', typ));
      sigContainer.appendChild(srow);
    });
    preview.appendChild(sigContainer);
    const applySigs = document.createElement('button'); applySigs.textContent='Apply edited signals'; applySigs.addEventListener('click', ()=>{ form._template_signals = collectSignalsFromPreview(preview); alert('Applied '+ (form._template_signals ? form._template_signals.length : 0) + ' signals'); });
    preview.appendChild(applySigs);
    form._template_signals = collectSignalsFromPreview(preview);
  }
}

function labelWith(labelText, el) {
  const wrapper = document.createElement('label'); wrapper.style.marginRight='8px'; wrapper.appendChild(document.createTextNode(labelText+': ')); wrapper.appendChild(el); return wrapper;
}

function collectPinsFromPreview(preview) {
  const rows = preview.querySelectorAll('.template-pin-row');
  const out = [];
  rows.forEach(r=>{
    const p = {};
    const num = r.querySelector('.tpl-physical'); if (num) p.physical_number = Number(num.value) || 0;
    const name = r.querySelector('.tpl-name'); if (name) p.name = name.value || '';
    const group = r.querySelector('.tpl-group'); if (group) p.group = group.value || p.name;
    const role = r.querySelector('.tpl-role-text'); if (role) p.role = role.value || '';
    const elec = r.querySelector('.tpl-elec-text'); if (elec) p.electrical = elec.value || '';
    const sup = r.querySelector('.tpl-supply'); if (sup && sup.value) { p.supply = { 'enum': sup.value }; }
    const volt = r.querySelector('.tpl-voltage'); if (volt && volt.value) { p.supply = p.supply || {}; p.supply.voltage_nominal = Number(volt.value); }
    const cur = r.querySelector('.tpl-current'); if (cur && cur.value) { p.supply = p.supply || {}; p.supply.current_max_a = Number(cur.value); }
    const g = r.querySelector('.tpl-ground-text'); if (g && g.value) p.ground = { ground_class: g.value };
    out.push(p);
  });
  return out;
}

function collectSignalsFromPreview(preview) {
  const rows = preview.querySelectorAll('.template-signal-row');
  const out = [];
  rows.forEach(r=>{
    const s = {};
    const prefix = r.querySelector('.tpl-s-prefix'); if (prefix) s.prefix = prefix.value || '';
    const count = r.querySelector('.tpl-s-count'); if (count) s.count = Number(count.value) || 1;
    const iface = r.querySelector('.tpl-s-interface'); if (iface) s.interface = iface.value || '';
    const typ = r.querySelector('.tpl-s-type'); if (typ) s.type = typ.value || '';
    out.push(s);
  });
  return out;
}

function addComponent() {
  const name = prompt('Component name (short)');
  if (!name) return;
  const comp = { name, devices: [] };
  components.push(comp);
  renderComponents();
}

function renderComponents() {
  const container = document.getElementById('components');
  container.innerHTML = '';
  components.forEach((cidx,c)=>{
    const el = document.createElement('div'); el.className='device';
    el.dataset.comp = cidx;
    el.innerHTML = `<strong>${c.name}</strong> <button data-idx="${cidx}" class="add-sensor">Add Sensor</button> <button data-idx="${cidx}" class="add-actuator">Add Actuator</button> <button data-idx="${cidx}" class="remove-component">Remove</button>`;
    const devicesDiv = document.createElement('div');
    c.devices.forEach((didx,d)=>{
      const ddiv = document.createElement('div'); ddiv.className='device'; ddiv.dataset.comp=cidx; ddiv.dataset.dev=didx;
      ddiv.innerHTML = `<strong>${d.name}</strong> <em>${d.type}</em> <button class="add-pin" data-comp="${cidx}" data-dev="${didx}">Add Pin</button> <button class="remove-device" data-comp="${cidx}" data-dev="${didx}">Remove</button>`;
      const pinsDiv = document.createElement('div');
      d.pins && d.pins.forEach(p=>{
        const pdiv = document.createElement('div'); pdiv.className='pin'; pdiv.textContent = `${p.connector||''} ${p.physical_number||''} ${p.name||''} [${p.group||''}] role=${p.role||''} type=${p.type||''}`;
        pinsDiv.appendChild(pdiv);
      });
      ddiv.appendChild(pinsDiv);
      devicesDiv.appendChild(ddiv);
    });
    el.appendChild(devicesDiv);
    container.appendChild(el);
  });

  // bind buttons
  document.querySelectorAll('.add-sensor').forEach(btn=>btn.addEventListener('click', ev=> showAddDeviceForm(Number(ev.target.dataset.idx), 'sensor')));
  document.querySelectorAll('.add-actuator').forEach(btn=>btn.addEventListener('click', ev=> showAddDeviceForm(Number(ev.target.dataset.idx), 'actuator')));
  document.querySelectorAll('.remove-component').forEach(btn=>btn.addEventListener('click', ev=>{ const idx=Number(ev.target.dataset.idx); if(confirm('Remove component '+components[idx].name+'?')){ components.splice(idx,1); renderComponents(); }}));
  document.querySelectorAll('.add-pin').forEach(btn=>btn.addEventListener('click', ev=>{ const comp=Number(ev.target.dataset.comp); const dev=Number(ev.target.dataset.dev); showAddPinForm(comp, dev); }));
  document.querySelectorAll('.remove-device').forEach(btn=>btn.addEventListener('click', ev=>{ const comp=Number(ev.target.dataset.comp); const dev=Number(ev.target.dataset.dev); if(confirm('Remove device?')){ components[comp].devices.splice(dev,1); renderComponents(); }}));
}

function showAddDeviceForm(componentIdx, deviceType) {
  const container = document.querySelector(`#components > div[data-comp='${componentIdx}']`);
  const form = document.createElement('div'); form.className='pin-form';
  // template selector
  let opts = '<option value="">-- blank --</option>';
  libraryTemplates.templates.filter(t=>t.type===deviceType).forEach(t=>{ opts += `<option value="${t.path}">${t.name}</option>`; });
  form.innerHTML = `
    <label>Name: <input class="type-target input-name"/></label>
    <label>Part number: <input class="input-pn"/></label>
    <label>Template: <select class="template-select">${opts}</select></label>
    <div class="template-preview"></div>
    <div><button class="save-device">Save</button> <button class="cancel-device">Cancel</button></div>
  `;
  container.appendChild(form);
  form.querySelectorAll('.type-target').forEach(i=>i.addEventListener('focus', (ev)=> setActiveField(ev.target)));

  const select = form.querySelector('.template-select');
  select.addEventListener('change', async ()=>{
    const path = select.value;
    const preview = form.querySelector('.template-preview'); preview.innerHTML = '';
    form._loaded_template = null; form._template_pins = null; form._template_signals = null;
    if (!path) return;
    try {
      const url = (path && path.charAt && path.charAt(0) === '/') ? path : ('/' + path);
      const r = await fetch(url);
      const j = await r.json();
      const nameVal = j.name || j['name'] || '';
      const pnVal = j.part_number || j['part_number'] || '';
      form.querySelector('.input-name').value = nameVal;
      form.querySelector('.input-pn').value = pnVal;
      form._loaded_template = j;
      renderTemplatePreview(preview, j, form);
    } catch (err) {
      preview.textContent = 'Failed to load template.';
    }
  });

  form.querySelector('.save-device').addEventListener('click', ()=>{
    const name = form.querySelector('.input-name').value || 'UnnamedDevice';
    const pn = form.querySelector('.input-pn').value || '';
    const dev = { name, part_number: pn, type: deviceType, pins: [] };
    if (form._template_pins && Array.isArray(form._template_pins)) {
      form._template_pins.forEach(p=> dev.pins.push(Object.assign({}, p)));
    } else if (form._loaded_template) {
      const t = form._loaded_template;
      const pins = Array.isArray(t.pins) ? t.pins : (Array.isArray(t['pins']) ? t['pins'] : []);
      pins.forEach(p=> dev.pins.push(Object.assign({}, p)));
    }
    if (form._template_signals && Array.isArray(form._template_signals)) {
      dev.signals = form._template_signals.map(s=> Object.assign({}, s));
    } else if (form._loaded_template) {
      const t = form._loaded_template;
      const signals = Array.isArray(t.signals) ? t.signals : (Array.isArray(t['signals']) ? t['signals'] : []);
      if (signals.length) dev.signals = signals.map(s=> Object.assign({}, s));
    }
    components[componentIdx].devices.push(dev);
    container.removeChild(form);
    renderComponents();
  });
  form.querySelector('.cancel-device').addEventListener('click', ()=>{ container.removeChild(form); });
}

function showAddPinForm(componentIdx, deviceIdx) {
  const compEl = document.querySelector(`#components > div[data-comp='${componentIdx}']`);
  // find device element
  const devEl = compEl.querySelector(`div.device[data-dev='${deviceIdx}']`);
  if (!devEl) return;
  const form = document.createElement('div'); form.className='pin-form';
  form.innerHTML = `
    <label>Connector: <input class="type-target input-connector"/></label>
    <label>Physical number: <input class="input-physical" type="number"/></label>
    <label>Name: <input class="type-target input-name"/></label>
    <label>Group: <input class="type-target input-group"/></label>
    <label>Role (token): <input class="type-target input-role" placeholder="EEC_PIN_ROLE_..."/></label>
    <label>Type: <input class="input-type" placeholder="DI/PWM/etc"/></label>
    <label>Interface (token): <input class="type-target input-interface" placeholder="EEC_SIGNAL_INTERFACE_..."/></label>
    <label>Supply enum token: <input class="type-target input-supply" placeholder="token or leave empty"/></label>
    <label>Voltage nominal: <input class="input-voltage" type="number" step="0.1"/></label>
    <label>Current max (A): <input class="input-current" type="number" step="0.1"/></label>
    <label>Ground class token: <input class="type-target input-groundclass" placeholder="LOGIC/POWER/UNCLASSIFIED or token"/></label>
    <div><button class="save-pin">Save pin</button> <button class="cancel-pin">Cancel</button></div>
  `;
  devEl.appendChild(form);
  form.querySelectorAll('.type-target').forEach(i=>i.addEventListener('focus', (ev)=> setActiveField(ev.target)));
  form.querySelector('.save-pin').addEventListener('click', ()=>{
    const p = {
      connector: form.querySelector('.input-connector').value,
      physical_number: Number(form.querySelector('.input-physical').value) || 0,
      name: form.querySelector('.input-name').value,
      group: form.querySelector('.input-group').value,
      role: form.querySelector('.input-role').value,
      type: form.querySelector('.input-type').value,
      electrical: form.querySelector('.input-interface').value,
      supply: undefined,
      ground: undefined
    };
    const vs = form.querySelector('.input-voltage').value; const cs = form.querySelector('.input-current').value;
    const supplyToken = form.querySelector('.input-supply').value;
    if (supplyToken || vs || cs) {
      p.supply = {};
      if (supplyToken) p.supply['enum'] = supplyToken;
      if (vs) p.supply['voltage_nominal'] = Number(vs);
      if (cs) p.supply['current_max_a'] = Number(cs);
    }
    const gclass = form.querySelector('.input-groundclass').value;
    if (gclass) p.ground = { ground_class: gclass };
    components[componentIdx].devices[deviceIdx].pins.push(p);
    devEl.removeChild(form);
    renderComponents();
  });
  form.querySelector('.cancel-pin').addEventListener('click', ()=>{ devEl.removeChild(form); });
}

function buildSystemJson() {
  const sys = {
    type: 'system',
    name: document.getElementById('system-name').value || 'Unnamed',
    version: document.getElementById('system-version').value || '1.0',
    priority: document.getElementById('system-priority').value || '',
    safety: document.getElementById('system-safety').value || '',
    system_level: Number(document.getElementById('system-level').value) || 1,
    components: []
  };
  components.forEach(c=>{
    const outc = { name: c.name, devices: [] };
    c.devices.forEach(d=>{
      const outd = { type: d.type, name: d.name, part_number: d.part_number || '', pins: [] };
      (d.pins||[]).forEach(p=>{
        const pcopy = {
          connector: p.connector,
          physical_number: p.physical_number,
          name: p.name,
          group: p.group,
          role: p.role,
          type: p.type,
          electrical: p.electrical
        };
        if (p.supply) pcopy.supply = p.supply;
        if (p.ground) pcopy.ground = p.ground;
        outd.pins.push(pcopy);
      });
      outc.devices.push(outd);
    });
    sys.components.push(outc);
  });
  return sys;
}

function downloadJSON(obj, filename) {
  const blob = new Blob([JSON.stringify(obj, null, 2)], {type:'application/json'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a'); a.href = url; a.download = filename || 'system.json';
  document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
}

function init() {
  document.getElementById('add-component').addEventListener('click', addComponent);
  document.getElementById('export-json').addEventListener('click', ()=>{
    const sys = buildSystemJson();
    document.getElementById('json-preview').textContent = JSON.stringify(sys, null, 2);
    downloadJSON(sys, (sys.name||'system') + '.json');
  });
  document.getElementById('download-sample').addEventListener('click', ()=>{
    const sample = { type:'system', name:'Example', version:'1.0', priority:'EEC_PRIORITY_LOW', safety:'EEC_SAFETY_QM', system_level:1, components:[] };
    downloadJSON(sample,'system-template.json');
  });

  document.addEventListener('focusin', (ev)=>{ if (ev.target.classList && ev.target.classList.contains('type-target')) setActiveField(ev.target); });

  // load types.json (from same folder as the editor)
  fetch('types.json').then(r=>{ if (!r.ok) throw new Error('types.json not found'); return r.json(); }).then(j=>{ types = j; document.getElementById('types-status').textContent = 'Loaded types.json'; renderTypesList(); }).catch(err=>{ document.getElementById('types-status').textContent = 'types.json not available — run the generator script.'; });

  // load library_templates.json (from same folder as the editor)
  fetch('library_templates.json').then(r=>{ if (!r.ok) throw new Error('library_templates.json not found'); return r.json(); }).then(j=>{ libraryTemplates = j; document.getElementById('types-status').textContent += ' • Loaded library templates'; }).catch(err=>{ console.warn('library_templates not available'); });
}

window.addEventListener('DOMContentLoaded', init);
