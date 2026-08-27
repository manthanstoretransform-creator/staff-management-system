import { baseApi } from './baseApi';

type ThunkParts = { dispatch: (action: any) => any; getState: () => any };

/**
 * Applies `recipe` to every cached variant of a query — every page, filter and
 * search term that currently sits in the cache — and hands back one undo for
 * the lot. The recipe receives the cache entry draft plus the arg it was
 * fetched with, so it can drop a row that no longer matches that view's filter.
 *
 * This is what lets a mutation show its result on the next frame instead of
 * waiting for a round trip and a refetch.
 */
export const patchEveryCachedQuery = (
  { dispatch, getState }: ThunkParts,
  endpointName: string,
  recipe: (draft: any, arg: any) => void,
) => {
  const cachedArgs = baseApi.util.selectCachedArgsForQuery(getState(), endpointName as never);
  const patches = Array.from(cachedArgs, (arg) =>
    dispatch(
      baseApi.util.updateQueryData(endpointName as never, arg as never, ((draft: any) =>
        recipe(draft, arg)) as never),
    ),
  );
  return { undo: () => patches.forEach((patch) => patch.undo()) };
};
