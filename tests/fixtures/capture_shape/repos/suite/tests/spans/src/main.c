/*
 * Cases of the comment search.
 */
#include <ztest.h>

/**
 * @brief Case direct
 *
 * @testid{S-direct}
 */
ZTEST(spans, test_direct)
{
	zassert_true(true);
}

/**
 * @brief Case blank
 *
 * @testid{S-blank}
 */

ZTEST(spans, test_blank)
{
	zassert_true(true);
}

/**
 * @brief Case blank_two
 *
 * @testid{S-blank_two}
 */


ZTEST(spans, test_blank_two)
{
	zassert_true(true);
}

/**
 * @brief Case blank_if
 *
 * @testid{S-blank_if}
 */

#if defined(CONFIG_X)
ZTEST(spans, test_blank_if)
{
	zassert_true(true);
}

/**
 * @brief Case ifdef
 *
 * @testid{S-ifdef}
 */
#ifdef CONFIG_X
ZTEST(spans, test_ifdef)
{
	zassert_true(true);
}

/**
 * @brief Case ifndef
 *
 * @testid{S-ifndef}
 */
#ifndef CONFIG_X
ZTEST(spans, test_ifndef)
{
	zassert_true(true);
}

/**
 * @brief Case elif
 *
 * @testid{S-elif}
 */
#elif defined(CONFIG_Y)
ZTEST(spans, test_elif)
{
	zassert_true(true);
}

/**
 * @brief Case else
 *
 * @testid{S-else}
 */
#else
ZTEST(spans, test_else)
{
	zassert_true(true);
}

/**
 * @brief Case endif
 *
 * @testid{S-endif}
 */
#endif
ZTEST(spans, test_endif)
{
	zassert_true(true);
}

/**
 * @brief Case plain
 *
 * @testid{S-plain}
 */
/* a plain comment */
ZTEST(spans, test_plain)
{
	zassert_true(true);
}

/**
 * @brief Case plain_multi
 *
 * @testid{S-plain_multi}
 */
/* a plain comment
 * over three
 * lines */
ZTEST(spans, test_plain_multi)
{
	zassert_true(true);
}

/**
 * @brief Case plain_indented
 *
 * @testid{S-plain_indented}
 */
    /* an indented plain comment */
ZTEST(spans, test_plain_indented)
{
	zassert_true(true);
}

/**
 * @brief Case mixed
 *
 * @testid{S-mixed}
 */
/* plain */

#if defined(CONFIG_X)

ZTEST(spans, test_mixed)
{
	zassert_true(true);
}

/**
 * @brief Case code
 *
 * @testid{S-code}
 */
static int counter;
ZTEST(spans, test_code)
{
	zassert_true(true);
}

/**
 * @brief Case include
 *
 * @testid{S-include}
 */
#include <string.h>
ZTEST(spans, test_include)
{
	zassert_true(true);
}

/**
 * @brief Case define
 *
 * @testid{S-define}
 */
#define LIMIT 4
ZTEST(spans, test_define)
{
	zassert_true(true);
}

/**
 * @brief Case linecomment
 *
 * @testid{S-linecomment}
 */
// a note
ZTEST(spans, test_linecomment)
{
	zassert_true(true);
}

/**
 * @brief Case doxline
 *
 * @testid{S-doxline}
 */
/// a line comment
ZTEST(spans, test_doxline)
{
	zassert_true(true);
}

/**
 * @brief Case codecloser
 *
 * @testid{S-codecloser}
 */
int y; /* trailing */
ZTEST(spans, test_codecloser)
{
	zassert_true(true);
}

ZTEST(spans, test_nodoc_code)
{
	zassert_true(true);
}

/* only a plain comment */
ZTEST(spans, test_nodoc_plain)
{
	zassert_true(true);
}

/*****
 * banner
 *****/
ZTEST(spans, test_nodoc_banner)
{
	zassert_true(true);
}


#if defined(CONFIG_X)
ZTEST(spans, test_nodoc_blank_if)
{
	zassert_true(true);
}

