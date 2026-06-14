import { useEffect, useState } from 'react';
import {
  listAddresses, createAddress, updateAddress, deleteAddress, setDefaultAddress,
} from '../api/addressesApi';

const EMPTY = { label: '', full_name: '', phone: '', line1: '', city: '', postal_code: '', is_default: false };

/** Saved-addresses manager: card grid + add/edit/delete + set default. */
const AddressBook = () => {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [form, setForm] = useState(null);     // null = closed; object = add/edit form data
  const [editingId, setEditingId] = useState(null);
  const [saving, setSaving] = useState(false);

  const load = () => {
    setLoading(true);
    listAddresses()
      .then((rows) => { setItems(rows); setError(''); })
      .catch((e) => setError(e?.message || 'Could not load addresses.'))
      .finally(() => setLoading(false));
  };
  useEffect(() => { load(); }, []);

  const openAdd = () => { setEditingId(null); setForm({ ...EMPTY, is_default: items.length === 0 }); };
  const openEdit = (a) => {
    setEditingId(a.id);
    setForm({ label: a.label || '', full_name: a.full_name || '', phone: a.phone || '',
      line1: a.line1 || '', city: a.city || '', postal_code: a.postal_code || '', is_default: !!a.is_default });
  };
  const closeForm = () => { setForm(null); setEditingId(null); setError(''); };

  const change = (k) => (e) => {
    const v = e.target.type === 'checkbox' ? e.target.checked : e.target.value;
    setForm((f) => ({ ...f, [k]: v }));
  };

  const submit = async (e) => {
    e.preventDefault();
    if (!form.line1.trim()) { setError('Street / house address is required.'); return; }
    setSaving(true);
    try {
      if (editingId) await updateAddress(editingId, form);
      else await createAddress(form);
      closeForm();
      load();
    } catch (err) {
      setError(err?.message || 'Could not save address.');
    } finally {
      setSaving(false);
    }
  };

  const remove = async (a) => {
    if (!window.confirm('Delete this address?')) return;
    try { await deleteAddress(a.id); load(); }
    catch (err) { setError(err?.message || 'Could not delete address.'); }
  };

  const makeDefault = async (a) => {
    try { await setDefaultAddress(a.id); load(); }
    catch (err) { setError(err?.message || 'Could not update default.'); }
  };

  return (
    <div className="addr-book">
      <header className="acc-head acc-head--row">
        <div>
          <h1>Saved addresses</h1>
          <p>{items.length} saved {items.length === 1 ? 'address' : 'addresses'}</p>
        </div>
        {!form && (
          <button type="button" className="acc-btn acc-btn--primary" onClick={openAdd}>
            + Add new address
          </button>
        )}
      </header>

      {error && <p className="acc-error" role="alert">{error}</p>}

      {/* Add / Edit form */}
      {form && (
        <form className="addr-form" onSubmit={submit}>
          <h3>{editingId ? 'Edit address' : 'New address'}</h3>
          <div className="addr-form-grid">
            <label className="addr-f addr-f--sm">
              <span>Label</span>
              <input value={form.label} onChange={change('label')} placeholder="Home, Office…" />
            </label>
            <label className="addr-f addr-f--sm">
              <span>Full name</span>
              <input value={form.full_name} onChange={change('full_name')} placeholder="Recipient name" />
            </label>
            <label className="addr-f addr-f--sm">
              <span>Phone</span>
              <input value={form.phone} onChange={change('phone')} placeholder="03xx-xxxxxxx" />
            </label>
            <label className="addr-f addr-f--full">
              <span>Street / house / area *</span>
              <input value={form.line1} onChange={change('line1')} placeholder="House #, street, area" required />
            </label>
            <label className="addr-f addr-f--sm">
              <span>City</span>
              <input value={form.city} onChange={change('city')} placeholder="Lahore" />
            </label>
            <label className="addr-f addr-f--sm">
              <span>Postal code</span>
              <input value={form.postal_code} onChange={change('postal_code')} placeholder="54000" />
            </label>
          </div>
          <label className="addr-default-check">
            <input type="checkbox" checked={form.is_default} onChange={change('is_default')} />
            <span>Set as default address</span>
          </label>
          <div className="addr-form-actions">
            <button type="submit" className="acc-btn acc-btn--primary" disabled={saving}>
              {saving ? 'Saving…' : (editingId ? 'Save changes' : 'Add address')}
            </button>
            <button type="button" className="acc-btn acc-btn--outline" onClick={closeForm} disabled={saving}>Cancel</button>
          </div>
        </form>
      )}

      {/* Cards */}
      {loading ? (
        <div className="acc-state"><div className="acc-spinner" /><p>Loading addresses…</p></div>
      ) : (!form && items.length === 0) ? (
        <div className="acc-state">
          <div className="acc-state__icon" aria-hidden="true">📍</div>
          <p>No saved addresses yet.</p>
          <button type="button" className="acc-btn acc-btn--primary" onClick={openAdd}>+ Add your first address</button>
        </div>
      ) : (
        <div className="addr-grid">
          {items.map((a) => (
            <article key={a.id} className={`addr-card ${a.is_default ? 'is-default' : ''}`}>
              <div className="addr-card-head">
                <span className="addr-card-label">{a.label || 'Address'}</span>
                {a.is_default && <span className="addr-default-badge">Default</span>}
              </div>
              {a.full_name && <p className="addr-card-name">{a.full_name}</p>}
              <p className="addr-card-line">{a.line1}</p>
              <p className="addr-card-sub">
                {[a.city, a.postal_code].filter(Boolean).join(' · ')}
              </p>
              {a.phone && <p className="addr-card-sub">{a.phone}</p>}
              <div className="addr-card-actions">
                <button type="button" className="acc-btn-link" onClick={() => openEdit(a)}>Edit</button>
                {!a.is_default && <button type="button" className="acc-btn-link" onClick={() => makeDefault(a)}>Set default</button>}
                <button type="button" className="acc-btn-link acc-btn-link--danger" onClick={() => remove(a)}>Delete</button>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
};

export default AddressBook;
