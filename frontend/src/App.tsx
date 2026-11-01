import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Activity, ArrowRight, Bell, Check, ChevronDown, CircleHelp, FileText, Filter,
  Globe2, LocateFixed, MapPin, Menu, Plus, Search, ShieldCheck, Siren, Upload, Users, X,
} from 'lucide-react'
import {
  Bar, BarChart, CartesianGrid, Cell, Line, LineChart, Pie, PieChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts'
import { MapContainer, Marker, Popup, TileLayer, useMapEvents } from 'react-leaflet'
import L from 'leaflet'
import { api } from './api'
import type { Dashboard, Department, Grievance } from './types'

const categories = ['Potholes and road damage', 'Garbage accumulation', 'Water leakage and flooding', 'Broken streetlights', 'Damaged public infrastructure', 'Drainage and sewage problems', 'Other civic issues']
const statuses = ['Submitted', 'AI Analysed', 'Verified', 'Assigned', 'In Progress', 'Resolved', 'Rejected']
const colors = ['#3165d4', '#28a47b', '#e4a126', '#df5c56', '#8063c9', '#19a2ac', '#788598']
const defaultCenter: [number, number] = [20, 0]

function pin(severity: string) {
  const color: Record<string, string> = { Critical: '#dc4545', High: '#f08c31', Medium: '#e5b332', Low: '#238b68' }
  return L.divIcon({ className: 'pin', html: `<span style="--pin:${color[severity] ?? '#3165d4'}"></span>`, iconSize: [22, 28], iconAnchor: [11, 26] })
}

function SelectPoint({ onSelect }: { onSelect: (point: [number, number]) => void }) {
  useMapEvents({ click: (event) => onSelect([event.latlng.lat, event.latlng.lng]) })
  return null
}

function MapView({ reports, onSelect, height = 300 }: { reports: Grievance[]; onSelect?: (point: [number, number]) => void; height?: number }) {
  const center = reports.length ? [reports[0].latitude, reports[0].longitude] as [number, number] : defaultCenter
  return <div className="map" style={{ height }}>
    <MapContainer center={center} zoom={reports.length ? 12 : 2} scrollWheelZoom>
      <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
      {onSelect && <SelectPoint onSelect={onSelect} />}
      {reports.map((item) => <Marker key={item.id} position={[item.latitude, item.longitude]} icon={pin(item.severity)}>
        <Popup><b>{item.grievance_number}</b><br />{item.category}<br />{item.severity} · {item.status}</Popup>
      </Marker>)}
    </MapContainer>
    {!reports.length && !onSelect && <div className="map-empty">No reports mapped yet</div>}
  </div>
}

function Modal({ title, close, children }: { title: string; close: () => void; children: React.ReactNode }) {
  return <div className="shade" onMouseDown={(e) => { if (e.target === e.currentTarget) close() }}>
    <section className="modal"><header><div><small>CIVICLENS</small><h2>{title}</h2></div><button className="icon-btn" onClick={close}><X size={18} /></button></header>{children}</section>
  </div>
}

export default function App() {
  const [page, setPage] = useState('Overview')
  const [metrics, setMetrics] = useState<Dashboard | null>(null)
  const [reports, setReports] = useState<Grievance[]>([])
  const [departments, setDepartments] = useState<Department[]>([])
  const [filters, setFilters] = useState({ category: '', severity: '', status: '' })
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [modal, setModal] = useState<'report' | 'login' | ''>('')
  const [point, setPoint] = useState<[number, number] | null>(null)
  const [address, setAddress] = useState('')
  const [trackId, setTrackId] = useState('')
  const [tracked, setTracked] = useState<Grievance | null>(null)
  const [trackError, setTrackError] = useState('')
  const [notice, setNotice] = useState('')
  const [token, setToken] = useState(localStorage.getItem('civiclens-token') ?? '')
  const [adminName, setAdminName] = useState(localStorage.getItem('civiclens-name') ?? '')
  const [busy, setBusy] = useState(false)

  const refresh = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const query = new URLSearchParams()
      Object.entries(filters).forEach(([key, value]) => { if (value) query.set(key, value) })
      const [d, r, deps] = await Promise.all([api.dashboard(), api.grievances(query.size ? `?${query}` : ''), api.departments()])
      setMetrics(d); setReports(r); setDepartments(deps)
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not load CivicLens data.') }
    finally { setLoading(false) }
  }, [filters])

  useEffect(() => { void refresh() }, [refresh])
  useEffect(() => {
    if (!notice) return
    const timer = window.setTimeout(() => setNotice(''), 4500)
    return () => window.clearTimeout(timer)
  }, [notice])
  useEffect(() => {
    if (page !== 'Track' || !tracked || tracked.status !== 'Submitted' || tracked.processing_error) return
    let active = true
    const timer = window.setTimeout(() => {
      void api.grievance(tracked.grievance_number).then((value) => { if (active) setTracked(value) })
        .catch((reason: unknown) => { if (active) setTrackError(reason instanceof Error ? reason.message : 'Could not refresh status.') })
    }, 3500)
    return () => { active = false; window.clearTimeout(timer) }
  }, [page, tracked])

  const filtered = useMemo(() => reports.filter((r) =>
    `${r.grievance_number} ${r.category} ${r.address}`.toLowerCase().includes(search.toLowerCase()),
  ), [reports, search])

  async function setLocation(value: [number, number]) {
    setPoint(value)
    const [geo] = await Promise.allSettled([api.geocode(...value), api.nearby(...value), api.weather(...value)])
    if (geo.status === 'fulfilled') setAddress(geo.value.display_name)
    else { setAddress(''); setNotice('Address lookup failed; the map pin will still be saved.') }
  }

  function locate() {
    navigator.geolocation?.getCurrentPosition(
      (pos) => { void setLocation([pos.coords.latitude, pos.coords.longitude]) },
      () => setNotice('Location unavailable. Select a point on the map instead.'),
      { enableHighAccuracy: true, timeout: 10000 },
    )
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!point) { setNotice('Please select a location on the map.'); return }
    setBusy(true)
    const form = new FormData(event.currentTarget)
    form.set('latitude', String(point[0])); form.set('longitude', String(point[1])); form.set('address', address)
    const file = form.get('image')
    if (file instanceof File && !file.size) form.delete('image')
    try {
      const result = await api.submit(form)
      setModal(''); setTracked(result); setTrackId(result.grievance_number); setTrackError('')
      setPage('Track'); setNotice(`Report submitted: ${result.grievance_number}`)
      setPoint(null); setAddress('')
      await refresh()
    } catch (reason) { setNotice(reason instanceof Error ? reason.message : 'Report submission failed.') }
    finally { setBusy(false) }
  }

  async function lookup(event: React.FormEvent) {
    event.preventDefault(); setTracked(null); setTrackError('')
    try { setTracked(await api.grievance(trackId.trim())) }
    catch (reason) { setTrackError(reason instanceof Error ? reason.message : 'Report not found.') }
  }

  async function login(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    try {
      const result = await api.login(String(data.get('email')), String(data.get('password')))
      if (result.role !== 'admin') throw new Error('Administrator access is required.')
      setToken(result.access_token); setAdminName(result.name)
      localStorage.setItem('civiclens-token', result.access_token); localStorage.setItem('civiclens-name', result.name)
      setModal(''); setPage('Operations')
    } catch (reason) { setNotice(reason instanceof Error ? reason.message : 'Sign in failed.') }
  }

  async function setStatus(report: Grievance, status: string) {
    try { await api.status(report.grievance_number, status, 'Updated from the operations desk.', token); await refresh() }
    catch (reason) { setNotice(reason instanceof Error ? reason.message : 'Could not update status.') }
  }

  async function addDepartment(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const formElement = event.currentTarget
    const data = new FormData(formElement)
    try {
      await api.addDepartment({
        name: String(data.get('name')), jurisdiction: String(data.get('jurisdiction')),
        contact_information: String(data.get('contact')), official_source_url: String(data.get('source')),
        verification_status: 'unverified',
      }, token)
      formElement.reset(); setNotice('Department added.'); await refresh()
    } catch (reason) { setNotice(reason instanceof Error ? reason.message : 'Could not add department.') }
  }

  const nav = ['Overview', 'Explore reports', 'Track', 'Operations', 'Departments']
  return <div className="shell">
    <aside className="sidebar">
      <div className="brand"><span className="brand-icon"><i /><i /><i /></span>civic<span>lens</span></div>
      <div className="community"><Globe2 size={17} /><div><small>COMMUNITY</small><b>City overview</b></div><ChevronDown size={14} /></div>
      <small className="nav-label">WORKSPACE</small>
      {nav.map((item, index) => <button key={item} className={`nav-link ${page === item ? 'selected' : ''}`} onClick={() => {
        if ((item === 'Operations' || item === 'Departments') && !token) setModal('login')
        else setPage(item)
      }}>{[Activity, MapPin, Search, ShieldCheck, Users].map((Icon, i) => i === index ? <Icon key={item} size={17} /> : null)}{item}</button>)}
      <div className="sidebar-foot"><div className="help"><CircleHelp size={18} /><b>Need a hand?</b><p>Report an issue and keep track of the progress.</p><button onClick={() => setModal('report')}>Make a report <ArrowRight size={13} /></button></div>
        <button className="profile" onClick={() => { if (token) { localStorage.clear(); setToken(''); setAdminName(''); setPage('Overview') } else setModal('login') }}><span>{adminName ? adminName[0].toUpperCase() : 'C'}</span><div><b>{adminName || 'Community member'}</b><small>{adminName ? 'Administrator' : 'Public access'}</small></div><ChevronDown size={14} /></button>
      </div>
    </aside>
    <main>
      <header className="topbar"><button className="menu mobile" onClick={() => setNotice('Use the navigation panel on a larger screen to switch pages.')}><Menu size={18} /></button><div className="crumb">Community <span>/</span> <b>{page}</b></div><div className="topright"><span className="live"><i /> Live data</span><button className="icon-btn"><Bell size={17} /></button></div></header>
      <div className="content">
        {error && <div className="error">{error}<button onClick={() => void refresh()}>Retry</button></div>}
        {loading && !metrics && <div className="loading">Connecting to community records…</div>}
        {page === 'Overview' && <Overview metrics={metrics} reports={reports} report={() => setModal('report')} go={setPage} />}
        {page === 'Explore reports' && <Explore reports={filtered} filters={filters} setFilters={setFilters} search={search} setSearch={setSearch} />}
        {page === 'Track' && <Track id={trackId} setId={setTrackId} report={tracked} error={trackError} lookup={lookup} reportNew={() => setModal('report')} />}
        {page === 'Operations' && (token ? <Operations reports={reports} update={setStatus} /> : <AdminGate login={() => setModal('login')} />)}
        {page === 'Departments' && (token ? <Departments items={departments} add={addDepartment} /> : <AdminGate login={() => setModal('login')} />)}
      </div>
      <footer>© {new Date().getFullYear()} CivicLens <span>·</span> Community data, handled with care</footer>
    </main>
    {modal === 'report' && <Modal title="Report a community issue" close={() => setModal('')}><form className="form" onSubmit={submit}>
      <label>Issue type<select name="category" required defaultValue=""><option value="" disabled>Select a category</option>{categories.map((c) => <option key={c}>{c}</option>)}</select></label>
      <label>Description<textarea name="description" minLength={10} maxLength={5000} required placeholder="What happened, and how does it affect the area?" /></label>
      <label className="file"><Upload size={17} /> Add a photo <small>JPG, PNG or WebP, max 10 MB</small><input type="file" name="image" accept="image/jpeg,image/png,image/webp" /></label>
      <div className="location-head"><b>Location</b><button type="button" className="secondary" onClick={locate}><LocateFixed size={14} /> Use my location</button></div>
      <p className="address">{address || (point ? `${point[0].toFixed(5)}, ${point[1].toFixed(5)}` : 'Click the map to pin your report.')}</p>
      <MapContainer center={point ?? defaultCenter} zoom={point ? 14 : 2} scrollWheelZoom className="report-map"><TileLayer attribution='&copy; OpenStreetMap' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" /><SelectPoint onSelect={(p) => void setLocation(p)} />{point && <Marker position={point} icon={pin('Medium')} />}</MapContainer>
      <button className="primary" disabled={busy}>{busy ? 'Submitting…' : 'Submit report'} <ArrowRight size={15} /></button>
    </form></Modal>}
    {modal === 'login' && <Modal title="Administrator sign in" close={() => setModal('')}><form className="form" onSubmit={login}><label>Email<input name="email" type="email" required /></label><label>Password<input name="password" type="password" minLength={10} required /></label><button className="primary">Sign in <ArrowRight size={15} /></button><small className="hint">Credentials are set in your local .env file.</small></form></Modal>}
    {notice && <div className="toast"><Check size={16} />{notice}<button onClick={() => setNotice('')}><X size={14} /></button></div>}
  </div>
}

function Overview({ metrics, reports, report, go }: { metrics: Dashboard | null; reports: Grievance[]; report: () => void; go: (page: string) => void }) {
  const stats = [
    ['Total reports', metrics?.total ?? 0, FileText, 'All submissions'],
    ['Open reports', metrics?.open ?? 0, Activity, 'Awaiting resolution'],
    ['Resolved', metrics?.resolved ?? 0, Check, 'Marked complete'],
    ['Priority', metrics?.priority ?? 0, Siren, 'High or critical'],
  ] as const
  const trend = (metrics?.trend ?? []).map(([date, count]) => ({ date: String(date).slice(5), reports: count }))
  const categoryData = (metrics?.categories ?? []).map(([name, value]) => ({ name, value }))
  const severity = metrics?.severities ?? []
  const routed = metrics?.departments?.map(([name, value]) => ({ name, value })) ?? []
  return <>
    <div className="welcome"><div><small className="eyebrow">YOUR COMMUNITY, IN FOCUS</small><h1>A clearer view of <em>what matters.</em></h1><p>See what’s happening around you. Help your neighborhood get the attention it deserves.</p></div><button className="primary" onClick={report}><Plus size={16} /> Report an issue</button></div>
    <section className="stats">{stats.map(([label, count, Icon, desc]) => <article className="stat" key={label}><div><Icon size={17} /></div><small>{label}</small><strong>{count.toLocaleString()}</strong><span>{desc}</span></article>)}</section>
    <section className="grid">
      <article className="card"><Heading kicker="COMMUNITY PULSE" title="Reports over time" />{trend.length ? <div className="chart"><ResponsiveContainer width="100%" height="100%"><LineChart data={trend}><CartesianGrid stroke="#edf0f4" vertical={false} /><XAxis dataKey="date" tickLine={false} axisLine={false} tick={{ fontSize: 10 }} /><YAxis allowDecimals={false} tickLine={false} axisLine={false} tick={{ fontSize: 10 }} /><Tooltip /><Line dataKey="reports" stroke="#3165d4" strokeWidth={2.5} dot={{ r: 3 }} /></LineChart></ResponsiveContainer></div> : <Empty title="No reports over time yet" />}</article>
      <article className="card"><Heading kicker="ISSUE MIX" title="By category" />{categoryData.length ? <><div className="donut"><ResponsiveContainer width="100%" height={185}><PieChart><Pie data={categoryData} dataKey="value" nameKey="name" innerRadius={52} outerRadius={76} paddingAngle={3}>{categoryData.map((_, i) => <Cell key={i} fill={colors[i % colors.length]} />)}</Pie><Tooltip /></PieChart></ResponsiveContainer><b>{metrics?.total ?? 0}<small> reports</small></b></div><div className="legend">{categoryData.slice(0, 5).map((item, i) => <span key={item.name}><i style={{ background: colors[i % colors.length] }} />{item.name}<b>{item.value}</b></span>)}</div></> : <Empty title="No category data yet" />}</article>
    </section>
    <section className="grid">
      <article className="card"><Heading kicker="ON THE MAP" title="Reports in your community" action={() => go('Explore reports')} /><MapView reports={reports} /></article>
      <article className="card"><Heading kicker="SERVICE HEALTH" title="Resolution snapshot" /><div className="resolution">{metrics?.average_resolution_hours == null ? '—' : `${metrics.average_resolution_hours}`}<small>{metrics?.average_resolution_hours == null ? '' : ' hrs average'}</small></div><p className="muted">Calculated from reports marked resolved in the database.</p><div className="severity">{['Critical', 'High', 'Medium', 'Low'].map((level) => { const n = severity.find(([name]) => name === level)?.[1] ?? 0; const max = Math.max(1, ...severity.map(([, value]) => value)); return <div key={level}><span>{level}</span><i><b className={level.toLowerCase()} style={{ width: `${n / max * 100}%` }} /></i><strong>{n}</strong></div> })}</div></article>
    </section>
    <section className="card"><Heading kicker="SERVICE OWNERSHIP" title="Department workload" />{routed.length ? <div className="bar-chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={routed}><CartesianGrid stroke="#edf0f4" vertical={false} /><XAxis dataKey="name" interval={0} tick={{ fontSize: 9 }} /><YAxis allowDecimals={false} tick={{ fontSize: 10 }} /><Tooltip /><Bar dataKey="value" name="Reports" fill="#3165d4" radius={[4, 4, 0, 0]} /></BarChart></ResponsiveContainer></div> : <Empty title="No department workload yet" />}</section>
    <section className="card"><Heading kicker="LATEST FROM THE COMMUNITY" title="Recent reports" action={() => go('Explore reports')} />{reports.length ? <Table reports={reports.slice(0, 6)} /> : <Empty title="No grievances have been submitted yet" />}</section>
  </>
}

function Heading({ kicker, title, action }: { kicker: string; title: string; action?: () => void }) {
  return <div className="heading"><div><small>{kicker}</small><h2>{title}</h2></div>{action && <button className="text-button" onClick={action}>View all <ArrowRight size={14} /></button>}</div>
}
function Empty({ title }: { title: string }) { return <div className="empty"><Globe2 size={22} /><b>{title}</b><span>Dashboard values reflect actual reports in your database.</span></div> }

function Table({ reports, update, inspect }: { reports: Grievance[]; update?: (r: Grievance, status: string) => void; inspect?: (r: Grievance) => void }) {
  return <div className="table-wrap"><table><thead><tr><th>REPORT</th><th>ISSUE TYPE</th><th>SEVERITY</th><th>STATUS</th><th>DATE</th>{update && <th>UPDATE</th>}</tr></thead><tbody>{reports.map((r) => <tr key={r.id}><td><button className="report-link" onClick={() => inspect?.(r)}><b>{r.grievance_number}</b><small>{r.address || `${r.latitude.toFixed(3)}, ${r.longitude.toFixed(3)}`}</small></button></td><td>{r.category}</td><td><span className={`badge ${r.severity.toLowerCase()}`}>{r.severity}</span></td><td>{r.status}</td><td>{new Date(r.created_at).toLocaleDateString()}</td>{update && <td><select value={r.status} onChange={(e) => update(r, e.target.value)}>{statuses.map((s) => <option key={s}>{s}</option>)}</select></td>}</tr>)}</tbody></table></div>
}

function Explore({ reports, filters, setFilters, search, setSearch }: { reports: Grievance[]; filters: { category: string; severity: string; status: string }; setFilters: (value: { category: string; severity: string; status: string }) => void; search: string; setSearch: (value: string) => void }) {
  return <><div className="welcome compact"><div><small className="eyebrow">COMMUNITY TRANSPARENCY</small><h1>Explore local <em>reports.</em></h1><p>Every marker and number comes from a real community submission.</p></div></div><div className="filters"><label><Search size={15} /><input placeholder="Search reports and locations" value={search} onChange={(e) => setSearch(e.target.value)} /></label><Filter size={15} />{(['category', 'severity', 'status'] as const).map((key) => <select key={key} value={filters[key]} onChange={(e) => setFilters({ ...filters, [key]: e.target.value })}><option value="">All {key}</option>{(key === 'category' ? categories : key === 'severity' ? ['Critical', 'High', 'Medium', 'Low'] : statuses).map((item) => <option key={item}>{item}</option>)}</select>)}</div><section className="card"><Heading kicker="GEOSPATIAL VIEW" title="Where reports are happening" /><MapView reports={reports} height={390} /></section><section className="card"><Heading kicker="PUBLIC RECORD" title="Community reports" />{reports.length ? <Table reports={reports} /> : <Empty title="No matching reports" />}</section></>
}

function Track({ id, setId, report, error, lookup, reportNew }: { id: string; setId: (value: string) => void; report: Grievance | null; error: string; lookup: (event: React.FormEvent) => void; reportNew: () => void }) {
  return <><div className="welcome compact"><div><small className="eyebrow">YOUR REPORT, YOUR RIGHT TO KNOW</small><h1>Follow the <em>progress.</em></h1><p>Enter the reference number you received when you reported the issue.</p></div></div><form className="track-search card" onSubmit={lookup}><Search size={19} /><input value={id} onChange={(e) => setId(e.target.value)} placeholder="CL-YYMMDD-XXXXXX" required /><button className="primary">Find my report <ArrowRight size={15} /></button></form>{error && <p className="error">{error}</p>}
    {report && <div className="grid tracking"><section className="card"><small className="eyebrow">REPORT DETAILS</small><h2>{report.category}</h2><p>{report.description}</p><MapView reports={[report]} height={210} /><p><MapPin size={14} /> {report.address || `${report.latitude}, ${report.longitude}`}</p><p><Users size={14} /> {report.report_count} reports linked</p>{report.department_name && <p><ShieldCheck size={14} /> {report.department_name}</p>}<h3>Priority score {report.severity_score}/100 · {report.severity}</h3>{report.severity_factors.map((f) => <small className="factor" key={f}>✓ {f}</small>)}{typeof report.ai_analysis.explanation === 'string' && <p>{report.ai_analysis.explanation}</p>}{report.processing_error && <p className="muted">AI analysis unavailable; report is saved.</p>}</section><section className="card"><Heading kicker="STATUS TIMELINE" title="Where things stand" />{report.history?.map((h) => <div className="history" key={`${h.new_status}-${h.created_at}`}><i /><b>{h.new_status}</b><small>{new Date(h.created_at).toLocaleString()}</small><p>{h.remarks}</p></div>)}<button className="secondary" onClick={reportNew}><Plus size={14} /> Report another issue</button></section></div>}
    {!report && !error && <section className="card"><Empty title="Your report details will appear here" /></section>}</>
}

function Operations({ reports, update }: { reports: Grievance[]; update: (r: Grievance, status: string) => void }) {
  return <><div className="welcome compact"><div><small className="eyebrow">AUTHORIZED STAFF</small><h1>Operations <em>desk.</em></h1><p>Review reports and keep the response moving.</p></div></div><section className="card"><Heading kicker="CASE MANAGEMENT" title="Community reports" />{reports.length ? <Table reports={reports} update={update} /> : <Empty title="No reports to action" />}</section><section className="card"><Heading kicker="GEOSPATIAL CONTEXT" title="Report locations" /><MapView reports={reports} /></section></>
}

function Departments({ items, add }: { items: Department[]; add: (event: React.FormEvent<HTMLFormElement>) => void }) {
  return <><div className="welcome compact"><div><small className="eyebrow">AUTHORITY DIRECTORY</small><h1>Responsible <em>departments.</em></h1><p>Manage authorities used for report routing.</p></div></div><div className="grid"><section className="card"><Heading kicker="CONFIGURED ROUTING" title="Department directory" />{items.length ? items.map((d) => <article className="department" key={d.id}><Users size={17} /><div><b>{d.name}</b><small>{d.jurisdiction || 'Jurisdiction not specified'}</small><small>{d.contact_information || 'No contact details'} · {d.verification_status}</small>{d.official_source_url && <a href={d.official_source_url} target="_blank" rel="noreferrer">Official source</a>}</div></article>) : <Empty title="No departments configured" />}</section><section className="card"><Heading kicker="ADMIN ACTION" title="Add an authority" /><form className="form" onSubmit={add}><label>Name<input name="name" required minLength={2} /></label><label>Jurisdiction<input name="jurisdiction" /></label><label>Contact<input name="contact" /></label><label>Official source URL<input name="source" type="url" /></label><button className="primary">Add department <ArrowRight size={14} /></button></form></section></div></>
}

function AdminGate({ login }: { login: () => void }) {
  return <section className="card gate"><ShieldCheck size={30} /><h2>Authorized staff workspace</h2><p>Sign in to manage report status and department routing.</p><button className="primary" onClick={login}>Administrator sign in <ArrowRight size={14} /></button></section>
}
