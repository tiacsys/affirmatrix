/*
 * Module mod_a.
 */
#include <ztest.h>

/**
 * @brief Shared name in tests/mod_a/src/more.c
 *
 * @testid{T-SHARED-A2}
 */
ZTEST(mod_a, test_shared)
{
	zassert_true(true);
}
