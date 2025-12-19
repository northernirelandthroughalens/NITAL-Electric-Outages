import React, { useState, useEffect, useMemo, useRef } from 'react';
import { 
  Zap, 
  Map as MapIcon, 
  AlertTriangle, 
  CheckCircle2, 
  RefreshCw, 
  Clock, 
  Navigation,
  Info
} from 'lucide-react';
import { 
  PieChart, 
  Pie, 
  Cell,
  Tooltip as RechartsTooltip,
  ResponsiveContainer
} from 'recharts';

/**
 * UTILITY: Mock Data Generator
 * Generates realistic fault data for Northern Ireland locations.
 */
const generateMockFaults = () => {
  const incidentTypes = ['Unplanned Outage', 'Planned Work', 'Equipment Fault', 'Storm Damage'];
  const locations = [
    { town: 'Belfast (South)', postcode: 'BT9', lat: 54.57, lng: -5.96 },
    { town: 'Bangor', postcode: 'BT19', lat: 54.66, lng: -5.67 },
    { town: 'Derry/Londonderry', postcode: 'BT48', lat: 55.00, lng: -7.34 },
    { town: 'Omagh', postcode: 'BT78', lat: 54.60, lng: -7.30 },
    { town: 'Newry', postcode: 'BT34', lat: 54.17, lng: -6.34 },
    { town: 'Lisburn', postcode: 'BT27', lat: 54.51, lng: -6.04 },
    { town: 'Ballymena', postcode: 'BT42', lat: 54.86, lng: -6.28 },
    { town: 'Enniskillen', postcode: 'BT74', lat: 54.34, lng: -7.64 },
    { town: 'Coleraine', postcode: 'BT51', lat: 55.13, lng: -6.66 },
    { town: 'Dungannon', postcode: 'BT70', lat: 54.50, lng: -6.77 },
    { town: 'Millisle', postcode: 'BT22', lat: 54.61, lng: -5.53 },
    { town: 'Antrim', postcode: 'BT41', lat: 54.71, lng: -6.22 },
    { town: 'Portadown', postcode: 'BT62', lat: 54.42, lng: -6.44 }
  ];

  const statuses = ['Investigating', 'Engineer Assigned', 'Engineer On Site', 'Work in Progress'];
  
  const faults = [];
  const count = Math.floor(Math.random() * 8) + 5; // 5-12 active faults
  const now = new Date(); // December 2025

  for (let i = 0; i < count; i++) {
    const loc = locations[Math.floor(Math.random() * locations.length)];
    const type = incidentTypes[Math.floor(Math.random() * incidentTypes.length)];
    const customers = Math.floor(Math.random() * 200) + 10;
    
    // Restoration time usually 2-4 hours from now
    const restoreTime = new Date(now.getTime() + (Math.random() * 4 * 60 * 60 * 1000));
    
    faults.push({
      id: `INC-${10000 + i}`,
      type,
      location: loc.town,
      postcode: loc.postcode,
      coordinates: [loc.lat, loc.lng],
      customersAffected: customers,
      status: statuses[Math.floor(Math.random() * statuses.length)],
      startTime: new Date(now.getTime() - (Math.random() * 2 * 60 * 60 * 1000)).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}),
      estRestoration: restoreTime.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}),
      message: "Our engineers are working to restore power as quickly as possible."
    });
  }
  return faults;
};

// --- COMPONENTS ---

const StatCard = ({ title, value, subtext, icon: Icon, color }) => (
  <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm flex items-start space-x-4">
    <div className={`p-3 rounded-lg ${color}`}>
      <Icon className="w-6 h-6 text-white" />
    </div>
    <div>
      <p className="text-slate-500 text-sm font-medium uppercase tracking-wide">{title}</p>
      <h3 className="text-2xl font-bold text-slate-900 mt-1">{value}</h3>
      {subtext && <p className="text-slate-400 text-xs mt-1">{subtext}</p>}
    </div>
  </div>
);

const Badge = ({ status }) => {
  const styles = {
    'Investigating': 'bg-amber-100 text-amber-800 border-amber-200',
    'Engineer Assigned': 'bg-blue-100 text-blue-800 border-blue-200',
    'Engineer On Site': 'bg-indigo-100 text-indigo-800 border-indigo-200',
    'Work in Progress': 'bg-purple-100 text-purple-800 border-purple-200',
    'Restored': 'bg-green-100 text-green-800 border-green-200'
  };
  return (
    <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold border ${styles[status] || 'bg-gray-100 text-gray-800'}`}>
      {status}
    </span>
  );
};

// --- LEAFLET CDN MAP COMPONENT ---
// Uses direct DOM manipulation via refs to work around build-time dependency issues.

const OSMMap = ({ faults, onSelect, selectedFault }) => {
  const mapContainerRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const markersLayerRef = useRef(null);
  const [libReady, setLibReady] = useState(false);

  // 1. Inject Leaflet CSS & JS
  useEffect(() => {
    if (window.L) {
      setLibReady(true);
      return;
    }

    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
    document.head.appendChild(link);

    const script = document.createElement('script');
    script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
    script.async = true;
    script.onload = () => setLibReady(true);
    document.body.appendChild(script);

    // Custom CSS for markers
    const style = document.createElement('style');
    style.innerHTML = `
      .marker-pin {
        width: 24px;
        height: 24px;
        border-radius: 50%;
        border: 2px solid white;
        box-shadow: 0 2px 4px rgba(0,0,0,0.3);
        display: block;
        transition: transform 0.2s;
      }
      .marker-pin:hover { transform: scale(1.1); }
      .marker-unplanned { background-color: #ef4444; }
      .marker-planned { background-color: #f59e0b; }
    `;
    document.head.appendChild(style);

    return () => {
      // Cleanup is tricky with CDNs, generally safe to leave in single-page context
    };
  }, []);

  // 2. Initialize Map
  useEffect(() => {
    if (!libReady || !mapContainerRef.current) return;

    if (!mapInstanceRef.current) {
      const L = window.L;
      const map = L.map(mapContainerRef.current, {
        zoomControl: false,
        scrollWheelZoom: true
      }).setView([54.65, -6.8], 8);

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors'
      }).addTo(map);

      // Create a layer group for markers to easily clear them later
      markersLayerRef.current = L.layerGroup().addTo(map);
      mapInstanceRef.current = map;
    }
  }, [libReady]);

  // 3. Update Markers
  useEffect(() => {
    if (!mapInstanceRef.current || !markersLayerRef.current || !libReady) return;

    const L = window.L;
    markersLayerRef.current.clearLayers();

    faults.forEach(fault => {
      const isUnplanned = fault.type === 'Unplanned Outage';
      const icon = L.divIcon({
        className: 'custom-div-icon',
        html: `<div class="marker-pin ${isUnplanned ? 'marker-unplanned' : 'marker-planned'}"></div>`,
        iconSize: [24, 24],
        iconAnchor: [12, 12],
        popupAnchor: [0, -12]
      });

      const marker = L.marker(fault.coordinates, { icon });
      
      // Bind popup
      const popupContent = `
        <div class="font-sans text-sm p-1">
          <strong class="block text-slate-900 mb-1">${fault.location}</strong>
          <span class="text-xs text-slate-500 block mb-1">${fault.type}</span>
          <span class="text-xs font-semibold text-green-700">Restoration: ${fault.estRestoration}</span>
        </div>
      `;
      marker.bindPopup(popupContent);

      // Handle click
      marker.on('click', () => {
        onSelect(fault);
      });

      markersLayerRef.current.addLayer(marker);
    });
  }, [faults, libReady, onSelect]);

  // 4. Handle FlyTo Selection
  useEffect(() => {
    if (selectedFault && mapInstanceRef.current && libReady) {
      mapInstanceRef.current.flyTo(selectedFault.coordinates, 11, { duration: 1.5 });
      // Optionally open popup for the selected one if we tracked marker instances mapped to IDs
    }
  }, [selectedFault, libReady]);

  return (
    <div className="bg-slate-100 rounded-xl overflow-hidden relative border border-slate-200 w-full h-[450px] z-0">
      <div ref={mapContainerRef} className="w-full h-full z-10" />
      
      {!libReady && (
        <div className="absolute inset-0 flex items-center justify-center bg-slate-50 z-20">
          <RefreshCw className="w-8 h-8 text-slate-400 animate-spin" />
        </div>
      )}

      <div className="absolute bottom-4 left-4 z-[400] bg-white/90 backdrop-blur px-3 py-2 rounded-lg text-xs font-medium text-slate-500 shadow-md border border-slate-200 pointer-events-none">
        Live OpenStreetMap Data
      </div>
    </div>
  );
};

export default function PowercheckDashboard() {
  const [faults, setFaults] = useState([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [selectedFault, setSelectedFault] = useState(null);
  const [dataSource, setDataSource] = useState('demo');

  // --- DATA FETCHING ---
  const fetchData = async () => {
    setLoading(true);
    const LIVE_API_URL = 'https://powercheck.nienetworks.co.uk/data/incidents.json'; 

    try {
      if (dataSource === 'live') {
        const response = await fetch(LIVE_API_URL);
        if (!response.ok) throw new Error("Network response was not ok");
        const data = await response.json();
        setFaults(data); 
      } else {
        await new Promise(resolve => setTimeout(resolve, 800));
        setFaults(generateMockFaults());
      }
      setLastUpdated(new Date());
    } catch (err) {
      console.warn("Live fetch failed, reverting to demo data.", err);
      setDataSource('demo');
      setFaults(generateMockFaults());
      setLastUpdated(new Date());
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 300000); 
    return () => clearInterval(interval);
  }, [dataSource]);

  // --- STATISTICS ---
  const stats = useMemo(() => {
    return {
      total: faults.length,
      customers: faults.reduce((acc, curr) => acc + curr.customersAffected, 0),
      critical: faults.filter(f => f.type === 'Unplanned Outage').length,
    };
  }, [faults]);

  const typeData = useMemo(() => {
    const data = {};
    faults.forEach(f => {
      data[f.type] = (data[f.type] || 0) + 1;
    });
    return Object.keys(data).map((k, i) => ({ 
      name: k, 
      value: data[k], 
      color: ['#ef4444', '#f59e0b', '#3b82f6', '#10b981'][i % 4] 
    }));
  }, [faults]);

  // --- RENDER ---
  return (
    <div className="min-h-screen bg-slate-50 font-sans text-slate-900 flex flex-col">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="bg-green-600 p-2 rounded-lg">
              <Zap className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-lg font-bold leading-tight">NIE Powercheck</h1>
              <p className="text-xs text-slate-500 font-medium">Live Outage Dashboard</p>
            </div>
          </div>
          
          <div className="flex items-center space-x-4">
            <div className="hidden md:flex items-center space-x-2 text-xs font-medium bg-slate-100 px-3 py-1.5 rounded-full text-slate-600">
               <span className={`w-2 h-2 rounded-full ${dataSource === 'live' ? 'bg-green-500' : 'bg-amber-500'}`}></span>
               <span>{dataSource === 'live' ? 'Connected to Live API' : 'Demo Mode'}</span>
            </div>
            <button 
              onClick={fetchData} 
              disabled={loading}
              className="p-2 hover:bg-slate-100 rounded-full transition-colors relative"
              title="Refresh Data"
            >
              <RefreshCw className={`w-5 h-5 text-slate-600 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>
      </header>

      <main className="flex-grow max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 w-full">
        
        {/* Top Stats Row */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <StatCard 
            title="Active Faults" 
            value={stats.total} 
            subtext="Currently reported across NI"
            icon={AlertTriangle} 
            color="bg-red-500"
          />
          <StatCard 
            title="Customers Affected" 
            value={stats.customers} 
            subtext="Estimated premises without power"
            icon={Zap} 
            color="bg-amber-500"
          />
          <StatCard 
            title="Restorations Today" 
            value={42} 
            subtext="Successfully resolved in last 24h"
            icon={CheckCircle2} 
            color="bg-green-500"
          />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          
          {/* Main Map Area (Spans 2 cols) */}
          <div className="lg:col-span-2 space-y-6">
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-1">
              <div className="p-4 border-b border-slate-100 flex justify-between items-center">
                <h2 className="font-bold text-slate-800 flex items-center">
                  <MapIcon className="w-5 h-5 mr-2 text-slate-500" />
                  Network Map (OpenStreetMap)
                </h2>
                <span className="text-xs text-slate-400">Updated: {lastUpdated?.toLocaleTimeString()}</span>
              </div>
              <div className="p-1">
                <OSMMap 
                  faults={faults} 
                  onSelect={setSelectedFault} 
                  selectedFault={selectedFault}
                />
              </div>
            </div>

            {/* Selected Incident Details */}
            {selectedFault ? (
              <div className="bg-white rounded-xl shadow-md border border-slate-200 overflow-hidden animate-in fade-in slide-in-from-bottom-4 duration-300">
                <div className="bg-slate-50 px-6 py-4 border-b border-slate-200 flex justify-between items-center">
                  <div>
                    <h3 className="font-bold text-lg text-slate-900">{selectedFault.location} ({selectedFault.postcode})</h3>
                    <p className="text-sm text-slate-500">Incident ID: {selectedFault.id}</p>
                  </div>
                  <button onClick={() => setSelectedFault(null)} className="text-slate-400 hover:text-slate-600">✕</button>
                </div>
                <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="space-y-4">
                    <div className="flex items-start">
                      <div className="mt-1 mr-3 bg-red-100 p-1.5 rounded-full"><AlertTriangle className="w-4 h-4 text-red-600"/></div>
                      <div>
                        <p className="text-xs text-slate-500 uppercase font-semibold">Incident Type</p>
                        <p className="font-medium">{selectedFault.type}</p>
                      </div>
                    </div>
                    <div className="flex items-start">
                      <div className="mt-1 mr-3 bg-blue-100 p-1.5 rounded-full"><Info className="w-4 h-4 text-blue-600"/></div>
                      <div>
                        <p className="text-xs text-slate-500 uppercase font-semibold">Status</p>
                        <div className="mt-1"><Badge status={selectedFault.status} /></div>
                      </div>
                    </div>
                  </div>
                  <div className="space-y-4">
                    <div className="flex items-start">
                      <div className="mt-1 mr-3 bg-amber-100 p-1.5 rounded-full"><Clock className="w-4 h-4 text-amber-600"/></div>
                      <div>
                        <p className="text-xs text-slate-500 uppercase font-semibold">Estimated Restoration</p>
                        <p className="font-bold text-lg text-slate-900">{selectedFault.estRestoration}</p>
                        <p className="text-xs text-slate-400">Reported at {selectedFault.startTime}</p>
                      </div>
                    </div>
                     <div className="flex items-start">
                      <div className="mt-1 mr-3 bg-slate-100 p-1.5 rounded-full"><Navigation className="w-4 h-4 text-slate-600"/></div>
                      <div>
                        <p className="text-xs text-slate-500 uppercase font-semibold">Message</p>
                        <p className="text-sm text-slate-600 leading-snug">{selectedFault.message}</p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
               <div className="bg-blue-50 border border-blue-100 rounded-xl p-6 text-center text-blue-800">
                 <p className="font-medium">Select a marker on the map to view detailed engineering updates.</p>
               </div>
            )}
          </div>

          {/* Sidebar / List & Charts */}
          <div className="space-y-6">
            
            {/* Fault List */}
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 flex flex-col h-[400px]">
              <div className="p-4 border-b border-slate-100">
                <h3 className="font-bold text-slate-800 flex items-center justify-between">
                  <span>Current Incidents</span>
                  <span className="text-xs bg-slate-100 px-2 py-1 rounded-full text-slate-600">{faults.length}</span>
                </h3>
              </div>
              <div className="overflow-y-auto flex-1 p-2 space-y-2">
                {faults.map(fault => (
                  <div 
                    key={fault.id}
                    onClick={() => setSelectedFault(fault)}
                    className={`p-3 rounded-lg border transition-all cursor-pointer hover:shadow-sm ${selectedFault?.id === fault.id ? 'bg-blue-50 border-blue-200 ring-1 ring-blue-300' : 'bg-white border-slate-100 hover:border-slate-300'}`}
                  >
                    <div className="flex justify-between items-start">
                      <div>
                        <p className="font-semibold text-sm text-slate-900">{fault.location}</p>
                        <p className="text-xs text-slate-500">{fault.postcode}</p>
                      </div>
                      <span className={`w-2 h-2 rounded-full mt-1.5 ${fault.type === 'Unplanned Outage' ? 'bg-red-500' : 'bg-amber-400'}`}></span>
                    </div>
                    <div className="mt-2 flex justify-between items-end">
                      <span className="text-xs text-slate-400">{fault.startTime}</span>
                      <span className="text-xs font-medium text-slate-600">{fault.status}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Mini Charts */}
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4">
              <h3 className="font-bold text-slate-800 mb-4 text-sm">Fault Types</h3>
              <div className="h-40 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={typeData}
                      cx="50%"
                      cy="50%"
                      innerRadius={40}
                      outerRadius={60}
                      paddingAngle={5}
                      dataKey="value"
                    >
                      {typeData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <RechartsTooltip contentStyle={{fontSize: '12px', borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)'}} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="flex flex-wrap gap-2 mt-2 justify-center">
                {typeData.map((entry, i) => (
                  <div key={i} className="flex items-center text-xs text-slate-500">
                    <span className="w-2 h-2 rounded-full mr-1" style={{backgroundColor: entry.color}}></span>
                    {entry.name}
                  </div>
                ))}
              </div>
            </div>

          </div>
        </div>

        {/* Disclaimer */}
        <div className="mt-8 text-center text-xs text-slate-400 max-w-2xl mx-auto">
          <p>
            Data provided for informational purposes only. "Demo Mode" uses simulated data based on typical NIE Networks fault patterns. 
            Do not rely on this dashboard for emergency safety information. Always treat downed power lines as live and dangerous.
          </p>
        </div>

      </main>

      {/* Footer Requirement */}
      <footer className="bg-white border-t border-slate-200 py-6 mt-auto">
        <div className="max-w-7xl mx-auto px-4 text-center">
           <a 
             href="https://nithroughalens.com" 
             target="_blank" 
             rel="noopener noreferrer"
             className="text-slate-500 hover:text-green-700 font-medium text-sm transition-colors"
           >
             Northern Ireland Through A Lens | 2025
           </a>
        </div>
      </footer>
    </div>
  );
}
