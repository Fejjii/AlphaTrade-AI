import { ValidationStage } from "@/components/validate/ValidationStage";
import type { ValidationStageModel } from "@/components/validate/types";

type ValidationPipelineProps = {
  stages: ValidationStageModel[];
  compact?: boolean;
};

export function ValidationPipeline({ stages, compact = false }: ValidationPipelineProps) {
  return (
    <section
      aria-labelledby="validation-pipeline-heading"
      data-testid="validation-pipeline"
      className="space-y-3"
    >
      <div>
        <h2 id="validation-pipeline-heading" className="text-lg font-semibold text-text-primary">
          Validation pipeline
        </h2>
        <p className="mt-1 text-sm text-text-muted">
          Draft → Candidate → Run plan → Run session → Observation → Outcome. Paper validation only.
        </p>
      </div>

      <ol
        className="flex flex-col gap-3"
        data-testid="validation-pipeline-stages"
        aria-label="Validation stages in order"
      >
        {stages.map((stage, index) => (
          <li key={stage.id}>
            <ValidationStage stage={stage} index={index} compact={compact} />
          </li>
        ))}
      </ol>
    </section>
  );
}
