import { Link } from "react-router-dom";
import type { StudyGroup } from "../../types/api";
import { roleLabel } from "../../utils/format";
import { Card } from "../../components/ui/Feedback";

export function GroupCard({ group }: { group: StudyGroup }) {
  return (
    <Card as="article" className="flex flex-col gap-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-stone-900">
            <Link to={`/app/groups/${group.id}`} className="hover:underline">
              {group.name}
            </Link>
          </h2>
          {group.course_code ? (
            <p className="mt-0.5 text-xs font-medium uppercase tracking-wide text-stone-500">
              {group.course_code}
            </p>
          ) : null}
        </div>
        <span className="rounded-full bg-stone-100 px-2 py-0.5 text-xs text-stone-700">
          {roleLabel(group.my_role)}
        </span>
      </div>
      <p className="line-clamp-3 text-sm text-stone-600">
        {group.description || "No description yet."}
      </p>
      <p className="text-xs text-stone-500">
        {group.member_count} {group.member_count === 1 ? "member" : "members"}
      </p>
    </Card>
  );
}
