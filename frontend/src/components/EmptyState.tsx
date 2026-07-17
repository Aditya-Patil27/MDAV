import type { LucideIcon } from "lucide-react";

export default function EmptyState({
  Icon,
  title,
  description,
  action,
}: {
  Icon: LucideIcon;
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex min-h-64 flex-col items-center justify-center rounded-lg border border-dashed border-gray-300 bg-white px-6 py-12 text-center">
      <span className="mb-4 flex h-11 w-11 items-center justify-center rounded-md bg-gray-100 text-gray-600">
        <Icon size={21} aria-hidden="true" />
      </span>
      <h2 className="text-base font-semibold text-gray-900">{title}</h2>
      <p className="mt-2 max-w-md text-sm leading-6 text-gray-600">{description}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}
