import { Button } from "../../components/ui/Button";
import type { Resource } from "../../types/api";
import { formatDate, fullName, linkHost } from "../../utils/format";

type ResourceListProps = {
  resources: Resource[];
  deletingId: string | null;
  onDelete: (resource: Resource) => void;
};

export function ResourceList({ resources, deletingId, onDelete }: ResourceListProps) {
  if (resources.length === 0) {
    return (
      <p className="rounded-lg border border-stone-200 bg-white p-8 text-center text-sm text-stone-500">
        No links shared yet.
      </p>
    );
  }

  return (
    <ul className="flex flex-col gap-3">
      {resources.map((resource) => (
        <li
          key={resource.id}
          className="rounded-lg border border-stone-200 bg-white p-4"
        >
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <a
                href={resource.url}
                target="_blank"
                // noopener stops the opened page from reaching back through
                // window.opener; noreferrer keeps the referrer off third
                // parties. Both matter for links any member can submit.
                rel="noopener noreferrer"
                className="font-medium text-teal-800 underline-offset-2 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-800"
              >
                {resource.title}
              </a>
              {/* The destination host, shown so nobody has to trust the name alone. */}
              <p className="mt-0.5 truncate text-xs text-stone-500">{linkHost(resource.url)}</p>
              {resource.description ? (
                <p className="mt-2 text-sm leading-6 text-stone-700">{resource.description}</p>
              ) : null}
              <p className="mt-2 text-xs text-stone-500">
                {resource.creator ? `Shared by ${fullName(resource.creator)}` : "Shared"} ·{" "}
                {formatDate(resource.created_at)}
              </p>
            </div>
            {resource.can_delete ? (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onDelete(resource)}
                loading={deletingId === resource.id}
                aria-label={`Remove ${resource.title}`}
              >
                Remove
              </Button>
            ) : null}
          </div>
        </li>
      ))}
    </ul>
  );
}
