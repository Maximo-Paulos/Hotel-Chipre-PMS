import { useMutation, type UseMutationOptions, type UseMutationResult } from "@tanstack/react-query";
import { useRef } from "react";

/**
 * useMutation wrapper that blocks a second `mutate()` call while one is
 * already in flight, using a ref instead of `mutation.isPending`.
 *
 * A rapid double-click/double-tap fires two native click handlers in the same
 * JS turn, before React re-renders a `disabled={mutation.isPending}` button —
 * `isPending` only flips on the NEXT render, too late to stop the second call.
 * Use this for any mutation whose duplicate execution creates a duplicate
 * real-world side effect (a charge, a reservation, a stock movement, ...).
 */
export function useGuardedMutation<TData = unknown, TError = unknown, TVariables = void, TContext = unknown>(
  options: UseMutationOptions<TData, TError, TVariables, TContext>
): UseMutationResult<TData, TError, TVariables, TContext> {
  const submittingRef = useRef(false);

  const mutation = useMutation<TData, TError, TVariables, TContext>({
    ...options,
    onSettled: (...args) => {
      submittingRef.current = false;
      return options.onSettled?.(...args);
    }
  });

  const guardedMutate: typeof mutation.mutate = (variables, mutateOptions) => {
    if (submittingRef.current) return;
    submittingRef.current = true;
    mutation.mutate(variables, mutateOptions);
  };

  const guardedMutateAsync: typeof mutation.mutateAsync = (variables, mutateOptions) => {
    if (submittingRef.current) return Promise.reject(new Error("mutation already in flight"));
    submittingRef.current = true;
    return mutation.mutateAsync(variables, mutateOptions);
  };

  return { ...mutation, mutate: guardedMutate, mutateAsync: guardedMutateAsync };
}
