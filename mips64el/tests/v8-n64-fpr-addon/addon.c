#include <node_api.h>
#include <stdint.h>

typedef struct {
  napi_env env;
  napi_value receiver;
  napi_value callback;
  napi_value result;
  napi_status status;
} ProbeContext;

/* The assembly wrapper calls the real N-API entry through this C bridge. */
__attribute__((noinline, visibility("hidden")))
void probe_invoke_js(ProbeContext* context) {
  context->status = napi_call_function(context->env, context->receiver,
                                      context->callback, 0, NULL,
                                      &context->result);
}

__attribute__((visibility("hidden")))
uint32_t probe_n64_fpr_roundtrip(ProbeContext* context);

static napi_value check_callee_saved(napi_env env, napi_callback_info info) {
  size_t argc = 1;
  ProbeContext context = {.env = env, .status = napi_generic_failure};
  napi_valuetype type;
  if (napi_get_cb_info(env, info, &argc, &context.callback,
                       &context.receiver, NULL) != napi_ok || argc != 1 ||
      napi_typeof(env, context.callback, &type) != napi_ok ||
      type != napi_function) {
    napi_throw_type_error(env, NULL, "checkCalleeSaved requires a callback");
    return NULL;
  }

  uint32_t mismatch_mask = probe_n64_fpr_roundtrip(&context);
  if (context.status != napi_ok) {
    bool pending = false;
    napi_is_exception_pending(env, &pending);
    if (!pending) napi_throw_error(env, NULL, "napi_call_function failed");
    return NULL;
  }
  napi_value result;
  if (napi_create_uint32(env, mismatch_mask, &result) != napi_ok) return NULL;
  return result;
}

NAPI_MODULE_INIT() {
  napi_value function;
  if (napi_create_function(env, "checkCalleeSaved", NAPI_AUTO_LENGTH,
                           check_callee_saved, NULL, &function) != napi_ok ||
      napi_set_named_property(env, exports, "checkCalleeSaved", function) !=
          napi_ok) {
    return NULL;
  }
  return exports;
}
