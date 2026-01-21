import React, { useState } from 'react';
import { Send, Plane, Calendar, Users, DollarSign, Filter } from 'lucide-react';

const InputField = ({ label, icon: Icon, ...props }) => (
    <div className="space-y-1">
        <label className="text-xs font-bold text-slate-500 uppercase flex items-center gap-1">
            <Icon size={12} /> {label}
        </label>
        <input
            {...props}
            className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none transition-all"
        />
    </div>
);

const SelectField = ({ label, icon: Icon, options, ...props }) => (
    <div className="space-y-1">
        <label className="text-xs font-bold text-slate-500 uppercase flex items-center gap-1">
            <Icon size={12} /> {label}
        </label>
        <select
            {...props}
            className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none transition-all appearance-none"
        >
            {options.map(opt => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
        </select>
    </div>
);

export default function TaskForm({ onSubmit }) {
    const [task, setTask] = useState({
        trip_type: 'round_trip',
        origin: '',
        destination: '',
        start_date: '',
        nights: 7,
        routing_codes: '',
        cabin: 'Cheapest available',
        adults: 1
    });

    const handleSubmit = (e) => {
        e.preventDefault();
        onSubmit(task);
    };

    return (
        <form onSubmit={handleSubmit} className="space-y-6">
            <div className="grid grid-cols-2 gap-4">
                <SelectField
                    label="Trip Type"
                    icon={Plane}
                    options={[
                        { label: 'Round Trip', value: 'round_trip' },
                        { label: 'One Way', value: 'one_way' }
                    ]}
                    value={task.trip_type}
                    onChange={(e) => setTask({ ...task, trip_type: e.target.value })}
                />
                <InputField
                    label="Start Date (MM/DD/YYYY)"
                    icon={Calendar}
                    placeholder="e.g. 02/01/2026"
                    value={task.start_date}
                    onChange={(e) => setTask({ ...task, start_date: e.target.value })}
                />
            </div>

            <div className="grid grid-cols-2 gap-4">
                <InputField
                    label="Origin"
                    icon={Filter}
                    placeholder="YVR"
                    value={task.origin}
                    onChange={(e) => setTask({ ...task, origin: e.target.value })}
                />
                <InputField
                    label="Destination"
                    icon={Filter}
                    placeholder="PVG"
                    value={task.destination}
                    onChange={(e) => setTask({ ...task, destination: e.target.value })}
                />
            </div>

            <div className="grid grid-cols-3 gap-4">
                <InputField
                    label="Nights"
                    icon={Calendar}
                    type="number"
                    value={task.nights}
                    onChange={(e) => setTask({ ...task, nights: parseInt(e.target.value) || 0 })}
                />
                <InputField
                    label="Adults"
                    icon={Users}
                    type="number"
                    value={task.adults}
                    onChange={(e) => setTask({ ...task, adults: parseInt(e.target.value) || 1 })}
                />
                <SelectField
                    label="Cabin"
                    icon={DollarSign}
                    options={[
                        { label: 'Cheapest', value: 'Cheapest available' },
                        { label: 'Premium Economy', value: 'Premium economy' },
                        { label: 'Business', value: 'Business class' },
                        { label: 'First', value: 'First class' }
                    ]}
                    value={task.cabin}
                    onChange={(e) => setTask({ ...task, cabin: e.target.value })}
                />
            </div>

            <InputField
                label="Airline Filter (Routing Codes)"
                icon={Filter}
                placeholder="e.g. C:MU+ (East China Search)"
                value={task.routing_codes}
                onChange={(e) => setTask({ ...task, routing_codes: e.target.value })}
            />

            <button
                type="submit"
                className="w-full gradient-bg text-white font-bold py-3 rounded-xl shadow-lg hover:opacity-90 transition-all flex items-center justify-center gap-2 mt-4"
            >
                <Send size={18} /> Launch Automated Scraper Task
            </button>
        </form>
    );
}
