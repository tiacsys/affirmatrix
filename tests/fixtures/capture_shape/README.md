# The capture shape fixture

Small synthetic inputs for the specifications of readers whose exports differ from
the first evidence fixture. They hold three repositories (`docs`, `suite`, `lib`),
three need exports, and Doxygen trees whose paths carry a prefix or name one test in
several directories. The C files only give the extractor text to read. They are never
compiled. No hash of any file here is pinned: each test computes its expected digest
from the files.
