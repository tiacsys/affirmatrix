/*
 * Module mod_b.
 */
#include <ztest.h>

/**
 * @brief Shared name in tests/mod_b/src/main.c
 *
 * @testid{T-SHARED-B}
 */
ZTEST(mod_b, test_shared)
{
	zassert_true(true);
}

/**
 * @brief gamma behaves
 *
 * @testid{T-GAMMA}
 */
ZTEST(mod_b, test_gamma)
{
	zassert_true(true);
}
