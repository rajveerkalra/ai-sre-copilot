import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type Point = { date?: string; label?: string; alerts?: number; confidence?: number };

export function AlertTrendChart({ data }: { data: Point[] }) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
        <CartesianGrid stroke="#e5ebef" vertical={false} />
        <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#5a6b76" }} axisLine={false} tickLine={false} />
        <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "#5a6b76" }} axisLine={false} tickLine={false} />
        <Tooltip
          contentStyle={{ borderRadius: 8, border: "1px solid #d5dee4", fontSize: 12 }}
        />
        <Bar dataKey="alerts" fill="#0d7a6f" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function ConfidenceChart({ data }: { data: Point[] }) {
  if (!data.length) {
    return <p className="muted empty">No investigation confidence yet.</p>;
  }
  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={data} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
        <CartesianGrid stroke="#e5ebef" vertical={false} />
        <XAxis dataKey="label" tick={{ fontSize: 10, fill: "#5a6b76" }} axisLine={false} tickLine={false} />
        <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: "#5a6b76" }} axisLine={false} tickLine={false} />
        <Tooltip
          contentStyle={{ borderRadius: 8, border: "1px solid #d5dee4", fontSize: 12 }}
        />
        <Line
          type="monotone"
          dataKey="confidence"
          stroke="#12202a"
          strokeWidth={2}
          dot={{ r: 3, fill: "#0d7a6f" }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
