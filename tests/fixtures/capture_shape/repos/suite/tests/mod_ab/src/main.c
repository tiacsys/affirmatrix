/*
 * Module mod_ab.
 */
#include <ztest.h>

/**
 * @brief Shared name in tests/mod_ab/src/main.c
 *
 * @testid{T-SHARED-AB}
 */
ZTEST(mod_ab, test_shared)
{
	zassert_true(true);
}
