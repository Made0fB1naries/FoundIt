% FoundIt matching and expiration rules.
% The Python module supplies the facts for each matching request.

:- dynamic item_category/2.
:- dynamic item_status/2.
:- dynamic item_campus/2.
:- dynamic item_word/2.
:- dynamic query_category/1.
:- dynamic query_campus/1.
:- dynamic query_word/1.

% A category must match when the user selected one.
% If no category was selected, keyword matching can still proceed.
category_is_compatible(PostId) :-
    query_category(Category),
    item_category(PostId, Category).

category_is_compatible(PostId) :-
    \+ query_category(_),
    item_category(PostId, _).

% A possible match must still be pending and share a keyword.
possible_match(PostId, Word) :-
    item_status(PostId, pending),
    category_is_compatible(PostId),
    item_word(PostId, Word),
    query_word(Word).

% Same-campus matches can be ranked higher by the Python wrapper.
same_campus_match(PostId) :-
    item_status(PostId, pending),
    item_campus(PostId, Campus),
    query_campus(Campus).

% Dates are passed as integer day numbers (Python date.toordinal()).
% FoundIt currently uses a seven-day retention period for claimed items.
claim_expired(ClaimedDay, TodayDay, RetentionDays) :-
    TodayDay - ClaimedDay >= RetentionDays.
