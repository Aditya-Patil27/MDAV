import StatusBadge from "./StatusBadge";

export default function DecisionBadge({
  decision,
  size = "md",
}: {
  decision: string | null | undefined;
  size?: "sm" | "md";
}) {
  return <StatusBadge decision={decision} size={size} />;
}
