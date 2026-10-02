/*
 * Module mod_a.
 */
#include <ztest.h>

/**
 * @brief Shared name in tests/mod_a/src/main.c
 *
 * @testid{T-SHARED-A}
 */
ZTEST(mod_a, test_shared)
{
	zassert_true(true);
}

/**
 * @brief alpha behaves
 *
 * @testid{T-ALPHA}
 */
ZTEST(mod_a, test_alpha)
{
	zassert_true(true);
}
