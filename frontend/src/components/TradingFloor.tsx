import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import type { TickPoint, Trade } from "../hooks/useWorkflow";

export function TradingFloor({ ticks, trades }: { ticks: TickPoint[]; trades: Record<string, Trade> }) {
  const data = ticks.slice(-50);
  const tradeList = Object.values(trades).slice(-15).reverse();
  return (
    <div className="grid grid-cols-3 gap-6">
      <div className="col-span-2 border border-border rounded p-4 bg-card h-72">
        <div className="text-xs uppercase tracking-widest text-foreground/60 mb-2">Price (last 50 ticks)</div>
        <ResponsiveContainer width="100%" height="90%">
          <LineChart data={data}>
            <XAxis dataKey="tick" stroke="#64748b" tick={{ fontSize: 10 }} />
            <YAxis domain={["auto", "auto"]} stroke="#64748b" tick={{ fontSize: 10 }} />
            <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #334155" }} />
            <Line type="monotone" dataKey="price" stroke="hsl(189 90% 55%)" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="border border-border rounded p-4 bg-card h-72 overflow-auto">
        <div className="text-xs uppercase tracking-widest text-foreground/60 mb-2">Trade Intents</div>
        <div className="font-mono text-xs space-y-2">
          {tradeList.length === 0 && <div className="text-foreground/40">awaiting ticks…</div>}
          {tradeList.map((t) => (
            <div key={t.trade_id} className="border-b border-border/60 pb-2">
              <div className="flex gap-2 items-baseline">
                <span className={"font-bold " + (t.action === "BUY" ? "text-emerald-300" :
                                                  t.action === "SELL" ? "text-rose-300" : "text-foreground/60")}>
                  {t.action}
                </span>
                <span>{t.qty}</span>
                {t.risk && (
                  <span className={"text-[10px] uppercase " +
                                   (t.risk.decision === "allow" ? "text-emerald-300" :
                                    t.risk.decision === "block" ? "text-rose-300" : "text-amber-300")}>
                    {t.risk.decision}
                  </span>
                )}
                {t.order && <span className="text-emerald-300 text-[10px]">✓ {t.order.order_id}</span>}
              </div>
              {t.rationale && <div className="text-foreground/50 text-[10px] truncate">{t.rationale}</div>}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
