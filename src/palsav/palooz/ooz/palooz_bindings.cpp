#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include <vector>

int Kraken_Decompress(const uint8_t *src, size_t src_len, uint8_t *dst,
                      size_t dst_len);

static PyObject* palooz_decompress(PyObject* self, PyObject* args) {
    char const* src_data;
    Py_ssize_t src_len;
    Py_ssize_t dst_len;

    if (!PyArg_ParseTuple(args, "y#n", &src_data, &src_len, &dst_len)) {
        return nullptr;
    }
    std::vector<uint8_t> dst((size_t)dst_len + 64);
    int rc;
    Py_BEGIN_ALLOW_THREADS
    rc = Kraken_Decompress(reinterpret_cast<uint8_t const *>(src_data),
                            static_cast<size_t>(src_len), dst.data(),
                            dst_len);
    Py_END_ALLOW_THREADS
    if (rc != dst_len) {
        PyErr_SetString(PyExc_RuntimeError, "Could not decompress requested amount");
        return nullptr;
    }
    return PyBytes_FromStringAndSize(reinterpret_cast<char const*>(dst.data()), dst_len);
}

struct CompressOptions;
struct LRMCascade;

int CompressBlock(int codec_id, uint8_t *src_in, uint8_t *dst_in, int src_size, int level,
                  const CompressOptions *compressopts, uint8_t *src_window_base, LRMCascade *lrm);

static PyObject* palooz_compress(PyObject* self, PyObject* args) {
    int codec_id;
    int level;
    uint8_t* src_data;
    Py_ssize_t src_len;
    Py_ssize_t dst_len;

    if (!PyArg_ParseTuple(args, "iiy#n", &codec_id, &level, &src_data, &src_len, &dst_len)) {
        return nullptr;
    }

    if (!src_data || src_len <= 0) {
        PyErr_SetString(PyExc_ValueError, "Invalid input data.");
        return nullptr;
    }

    size_t dst_capacity = static_cast<size_t>(src_len) + 65536;
    std::vector<uint8_t> dst(dst_capacity);
    int rc;
    Py_BEGIN_ALLOW_THREADS
    rc = CompressBlock(codec_id, src_data, dst.data(), src_len, level, nullptr, nullptr, nullptr);
    Py_END_ALLOW_THREADS

    if (rc < 0 || rc > static_cast<int>(dst_capacity)) {
        PyErr_SetString(PyExc_RuntimeError, "Compression failed or invalid output size");
        return nullptr;
    }
    return PyBytes_FromStringAndSize(reinterpret_cast<char const*>(dst.data()), rc);
}

static PyMethodDef PaloozMethods[] = {
    {"decompress", palooz_decompress, METH_VARARGS, "Decompress a block of data."},
    {"compress", palooz_compress, METH_VARARGS, "Compress a block of data."},
    {nullptr, nullptr, 0, nullptr},
};

static char const* palooz_doc = "Bindings for palooz.";

static struct PyModuleDef paloozmodule = {
    PyModuleDef_HEAD_INIT,
    "palooz",
    palooz_doc,
    -1,
    PaloozMethods,
};

PyMODINIT_FUNC
PyInit_palooz(void) {
    return PyModule_Create(&paloozmodule);
}
