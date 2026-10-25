from dataclasses import dataclass


@dataclass(frozen=True)
class AcademicMaterialSample:
    """Represents a real-world university lecture handout or academic PDF material."""

    sample_id: int
    filename: str
    discipline: str
    query: str
    expected_entities: tuple[str, ...]
    content: str


def build_valid_pdf_bytes(text_content: str) -> bytes:
    """Construct a standards-compliant PDF-1.4 document in memory containing the given text."""
    lines = [line.strip() for line in text_content.splitlines() if line.strip()]
    stream_commands = ["BT", "/F1 11 Tf", "50 760 Td", "14 TL"]
    for line in lines:
        ascii_safe = (
            line.encode("latin-1", errors="replace").decode("latin-1")
            .replace("\\", "\\\\")
            .replace("(", "\\(")
            .replace(")", "\\)")
        )
        stream_commands.append(f"({ascii_safe}) Tj T*")
    stream_commands.append("ET")
    stream_data = "\n".join(stream_commands).encode("latin-1")

    objects: list[bytes] = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n",
        b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
        f"5 0 obj\n<< /Length {len(stream_data)} >>\nstream\n".encode("latin-1")
        + stream_data
        + b"\nendstream\nendobj\n",
    ]

    pdf = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for obj in objects:
        offsets.append(len(pdf))
        pdf.extend(obj)

    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))

    pdf.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode(
            "latin-1"
        )
    )
    return bytes(pdf)


TWENTY_ACADEMIC_MATERIALS: tuple[AcademicMaterialSample, ...] = (
    AcademicMaterialSample(
        sample_id=1,
        filename="01_cellular_biology.pdf",
        discipline="Cellular Biology",
        query="Mitochondria Chloroplasts and Ribosomes in Eukaryotic Cells",
        expected_entities=("Mitochondria", "Chloroplasts", "Ribosomes", "Cell Membrane"),
        content=(
            "# Cellular Biology and Organelles\n"
            "Mitochondria: Organelles that generate ATP chemical energy via cellular respiration.\n"
            "Chloroplasts: Plastids in plant cells that capture sunlight for photosynthesis.\n"
            "Ribosomes: Molecular machines responsible for protein synthesis from mRNA.\n"
            "Cell Membrane: Phospholipid bilayer regulating selective transport of ions."
        ),
    ),
    AcademicMaterialSample(
        sample_id=2,
        filename="02_thermodynamics.pdf",
        discipline="Physics - Thermodynamics",
        query="Laws of Thermodynamics Entropy and Enthalpy",
        expected_entities=("Zeroth Law", "First Law", "Second Law", "Entropy"),
        content=(
            "# Classical Thermodynamics\n"
            "Zeroth Law: Defines thermal equilibrium and forms the basis of temperature measurement.\n"
            "First Law: Conservation of energy stating that internal energy equals heat minus work.\n"
            "Second Law: Isolated systems spontaneously evolve toward thermodynamic equilibrium.\n"
            "Entropy: Quantitative measure of molecular disorder and unavailable thermal energy."
        ),
    ),
    AcademicMaterialSample(
        sample_id=3,
        filename="03_data_structures.pdf",
        discipline="Computer Science - Data Structures",
        query="Hash Tables Binary Search Trees and Graphs",
        expected_entities=("Hash Table", "Binary Search Tree", "Heap", "Adjacency List"),
        content=(
            "# Fundamental Data Structures\n"
            "Hash Table: Key-value structure providing amortized constant-time lookup via hash functions.\n"
            "Binary Search Tree: Hierarchical node tree maintaining sorted order for logarithmic search.\n"
            "Heap: Complete binary tree satisfying the heap property for priority queues.\n"
            "Adjacency List: Compact representation of sparse graphs storing neighbor lists per vertex."
        ),
    ),
    AcademicMaterialSample(
        sample_id=4,
        filename="04_neurodiversity_education.pdf",
        discipline="Inclusive Education & Neurobiology",
        query="Visual Learning Strategies for ADHD ASD and Deaf Students",
        expected_entities=("Cognitive Overload", "Visual Scaffolding", "Sign Language", "Executive Function"),
        content=(
            "# Accessible Pedagogy and Neurodiversity\n"
            "Cognitive Overload: Excessive working memory demand caused by dense unstructured text.\n"
            "Visual Scaffolding: Diagrams and mind maps that externalize logical relationships.\n"
            "Sign Language: Spatial-visual linguistic modality native to deaf learners.\n"
            "Executive Function: Prefrontal cognitive processes governing attention and task planning."
        ),
    ),
    AcademicMaterialSample(
        sample_id=5,
        filename="05_clean_architecture.pdf",
        discipline="Software Engineering",
        query="Clean Architecture Dependency Rule Entities and Use Cases",
        expected_entities=("Entities", "Use Cases", "Interface Adapters", "Dependency Rule"),
        content=(
            "# Clean Architecture in Modern Backend Systems\n"
            "Entities: Enterprise-wide business rules encapsulated against external changes.\n"
            "Use Cases: Application-specific orchestration rules coordinating data flow.\n"
            "Interface Adapters: Routers and repositories converting data formats for frameworks.\n"
            "Dependency Rule: Source code dependencies must point strictly inward toward domain logic."
        ),
    ),
    AcademicMaterialSample(
        sample_id=6,
        filename="06_vector_databases_rag.pdf",
        discipline="Artificial Intelligence",
        query="Retrieval Augmented Generation Vector Embeddings and Cosine Similarity",
        expected_entities=("Vector Embeddings", "Cosine Similarity", "Semantic Chunking", "Grounded Generation"),
        content=(
            "# Retrieval-Augmented Generation Systems\n"
            "Vector Embeddings: Dense numerical representations capturing semantic meaning in high dimensions.\n"
            "Cosine Similarity: Metric measuring the cosine of the angle between two non-zero vectors.\n"
            "Semantic Chunking: Partitioning documents by logical headers and overlapping windows.\n"
            "Grounded Generation: Restricting LLM synthesis exclusively to retrieved factual context."
        ),
    ),
    AcademicMaterialSample(
        sample_id=7,
        filename="07_constitutional_law.pdf",
        discipline="Constitutional Law",
        query="Separation of Powers Fundamental Rights and Judicial Review",
        expected_entities=("Separation of Powers", "Fundamental Rights", "Judicial Review", "Due Process"),
        content=(
            "# Principles of Constitutional Law\n"
            "Separation of Powers: Division of state authority into legislative executive and judicial branches.\n"
            "Fundamental Rights: Constitutional guarantees protecting individual liberty and equality.\n"
            "Judicial Review: Power of courts to invalidate statutes that violate the constitution.\n"
            "Due Process: Legal requirement that the state respect all statutory rights owed to a person."
        ),
    ),
    AcademicMaterialSample(
        sample_id=8,
        filename="08_macroeconomics.pdf",
        discipline="Economics",
        query="Gross Domestic Product Inflation Monetary Policy and Fiscal Policy",
        expected_entities=("Gross Domestic Product", "Inflation", "Monetary Policy", "Fiscal Policy"),
        content=(
            "# Macroeconomic Indicators and Policies\n"
            "Gross Domestic Product: Total monetary value of finished goods and services produced.\n"
            "Inflation: Sustained increase in the general price level of goods over time.\n"
            "Monetary Policy: Central bank management of interest rates and money supply.\n"
            "Fiscal Policy: Government taxation and public spending decisions influencing aggregate demand."
        ),
    ),
    AcademicMaterialSample(
        sample_id=9,
        filename="09_organic_chemistry.pdf",
        discipline="Organic Chemistry",
        query="Covalent Bonding Hydrocarbons Functional Groups and Isomerism",
        expected_entities=("Covalent Bonding", "Hydrocarbons", "Functional Groups", "Stereoisomerism"),
        content=(
            "# Foundations of Organic Chemistry\n"
            "Covalent Bonding: Sharing of electron pairs between carbon atoms forming stable chains.\n"
            "Hydrocarbons: Compounds consisting entirely of hydrogen and carbon such as alkanes.\n"
            "Functional Groups: Specific substituent moieties governing chemical reactivity.\n"
            "Stereoisomerism: Isomers sharing atomic connectivity but differing in spatial arrangement."
        ),
    ),
    AcademicMaterialSample(
        sample_id=10,
        filename="10_computer_networks.pdf",
        discipline="Computer Networks",
        query="OSI Model TCP Handshake DNS Resolution and HTTP Protocol",
        expected_entities=("OSI Model", "TCP Handshake", "DNS Resolution", "TLS Encryption"),
        content=(
            "# Computer Networking Protocols\n"
            "OSI Model: Seven-layer conceptual framework standardizing telecommunication functions.\n"
            "TCP Handshake: Three-way SYN SYN-ACK ACK exchange establishing reliable transport.\n"
            "DNS Resolution: Hierarchical translation of human-readable domain names into IP addresses.\n"
            "TLS Encryption: Cryptographic protocol securing application data in transit."
        ),
    ),
    AcademicMaterialSample(
        sample_id=11,
        filename="11_linear_algebra.pdf",
        discipline="Mathematics - Linear Algebra",
        query="Vector Spaces Eigenvalues Matrix Decomposition and Orthogonality",
        expected_entities=("Vector Spaces", "Eigenvalues", "Orthogonality", "Singular Value Decomposition"),
        content=(
            "# Linear Algebra for Data Science\n"
            "Vector Spaces: Collections of vectors closed under addition and scalar multiplication.\n"
            "Eigenvalues: Scalar factors by which eigenvectors are stretched during linear transformations.\n"
            "Orthogonality: Generalization of perpendicularity where the inner product equals zero.\n"
            "Singular Value Decomposition: Factorization of a matrix into rotation and scaling components."
        ),
    ),
    AcademicMaterialSample(
        sample_id=12,
        filename="12_ecology_ecosystems.pdf",
        discipline="Ecology & Environmental Science",
        query="Trophic Levels Carbon Cycle Biodiversity and Nitrogen Fixation",
        expected_entities=("Trophic Levels", "Carbon Cycle", "Biodiversity", "Nitrogen Fixation"),
        content=(
            "# Ecosystem Dynamics and Biogeochemical Cycles\n"
            "Trophic Levels: Hierarchical positions organisms occupy in an ecological food web.\n"
            "Carbon Cycle: Continuous exchange of carbon among biosphere atmosphere and oceans.\n"
            "Biodiversity: Variety and variability of life across genetic species and ecosystem levels.\n"
            "Nitrogen Fixation: Conversion of atmospheric nitrogen into ammonia by symbiotic bacteria."
        ),
    ),
    AcademicMaterialSample(
        sample_id=13,
        filename="13_operating_systems.pdf",
        discipline="Computer Science - Operating Systems",
        query="Process Scheduling Virtual Memory Deadlocks and Semaphores",
        expected_entities=("Process Scheduling", "Virtual Memory", "Deadlock", "Semaphores"),
        content=(
            "# Operating System Internals\n"
            "Process Scheduling: Kernel multiplexing of CPU time slices across ready threads.\n"
            "Virtual Memory: Hardware-assisted abstraction mapping logical pages to physical frames.\n"
            "Deadlock: State where concurrent processes block indefinitely waiting for held resources.\n"
            "Semaphores: Atomic synchronization primitives controlling access to shared critical sections."
        ),
    ),
    AcademicMaterialSample(
        sample_id=14,
        filename="14_statistics_probability.pdf",
        discipline="Statistics & Probability",
        query="Bayes Theorem Normal Distribution Central Limit Theorem and Hypothesis Testing",
        expected_entities=("Bayes Theorem", "Normal Distribution", "Central Limit Theorem", "Hypothesis Testing"),
        content=(
            "# Statistical Inference and Probability Theory\n"
            "Bayes Theorem: Mathematical rule updating conditional probabilities given new evidence.\n"
            "Normal Distribution: Symmetric bell-shaped Gaussian probability density function.\n"
            "Central Limit Theorem: Sample means converge to a normal distribution as sample size grows.\n"
            "Hypothesis Testing: Formal procedure evaluating null hypotheses using p-values and alpha levels."
        ),
    ),
    AcademicMaterialSample(
        sample_id=15,
        filename="15_quantum_mechanics.pdf",
        discipline="Physics - Quantum Mechanics",
        query="Wave Particle Duality Schrodinger Equation Superposition and Entanglement",
        expected_entities=("Wave Particle Duality", "Schrodinger Equation", "Quantum Superposition", "Quantum Entanglement"),
        content=(
            "# Introduction to Quantum Mechanics\n"
            "Wave Particle Duality: Quantum entities exhibit both wave-like and particle-like properties.\n"
            "Schrodinger Equation: Differential equation governing the time evolution of wave functions.\n"
            "Quantum Superposition: Principle that a physical system exists in linear combinations of eigenstates.\n"
            "Quantum Entanglement: Non-local correlation between quantum states of separated particles."
        ),
    ),
    AcademicMaterialSample(
        sample_id=16,
        filename="16_database_systems.pdf",
        discipline="Database Systems",
        query="ACID Transactions Relational Normalization B-Tree Indexes and MVCC",
        expected_entities=("ACID Transactions", "Normalization", "B-Tree Index", "Concurrency Control"),
        content=(
            "# Relational and Vector Database Internals\n"
            "ACID Transactions: Atomicity Consistency Isolation and Durability guarantees for reliable storage.\n"
            "Normalization: Structuring relational tables to minimize data redundancy and anomalies.\n"
            "B-Tree Index: Self-balancing search tree accelerating range and equality queries.\n"
            "Concurrency Control: Multi-version isolation ensuring readers do not block writers."
        ),
    ),
    AcademicMaterialSample(
        sample_id=17,
        filename="17_lgpd_data_privacy.pdf",
        discipline="Information Security & LGPD",
        query="LGPD Data Minimization Anonymization Prompt Injection Defense and Local LLMs",
        expected_entities=("Data Minimization", "Anonymization", "Prompt Injection Defense", "Local Inference"),
        content=(
            "# Data Protection Ethics and LGPD in Generative AI\n"
            "Data Minimization: Processing only the strictly necessary personal and institutional data.\n"
            "Anonymization: Irreversible removal of personally identifiable markers from datasets.\n"
            "Prompt Injection Defense: Input sanitization blocking malicious instruction overrides.\n"
            "Local Inference: Executing open-source models via Ollama to prevent external data leakage."
        ),
    ),
    AcademicMaterialSample(
        sample_id=18,
        filename="18_epistemology_science.pdf",
        discipline="Philosophy of Science",
        query="Empiricism Falsifiability Paradigm Shifts and Scientific Method",
        expected_entities=("Empiricism", "Falsifiability", "Paradigm Shift", "Peer Review"),
        content=(
            "# Epistemology and Methodology of Science\n"
            "Empiricism: Epistemological view that knowledge arises primarily from sensory observation.\n"
            "Falsifiability: Popperian criterion requiring scientific theories to be testable and refutable.\n"
            "Paradigm Shift: Kuhnian revolution replacing dominant scientific frameworks with new models.\n"
            "Peer Review: Critical evaluation of research manuscripts by independent domain experts."
        ),
    ),
    AcademicMaterialSample(
        sample_id=19,
        filename="19_human_physiology.pdf",
        discipline="Human Physiology",
        query="Homeostasis Action Potential Synaptic Transmission and Endocrine Feedback",
        expected_entities=("Homeostasis", "Action Potential", "Synaptic Transmission", "Endocrine Feedback"),
        content=(
            "# Human Neurophysiology and Homeostasis\n"
            "Homeostasis: Self-regulating physiological process maintaining internal stability.\n"
            "Action Potential: Rapid depolarization and repolarization propagating along neuronal axons.\n"
            "Synaptic Transmission: Chemical release of neurotransmitters across the synaptic cleft.\n"
            "Endocrine Feedback: Hormonal negative feedback loops regulating metabolism and growth."
        ),
    ),
    AcademicMaterialSample(
        sample_id=20,
        filename="20_distributed_systems.pdf",
        discipline="Distributed Systems",
        query="CAP Theorem Consensus Algorithms Idempotency and Circuit Breakers",
        expected_entities=("CAP Theorem", "Consensus Algorithms", "Idempotency", "Circuit Breaker"),
        content=(
            "# Resilient Distributed Systems\n"
            "CAP Theorem: Trade-off among Consistency Availability and Partition Tolerance in clusters.\n"
            "Consensus Algorithms: Protocols such as Raft ensuring distributed nodes agree on state.\n"
            "Idempotency: Property guaranteeing repeated operations yield the exact same state result.\n"
            "Circuit Breaker: Fault-tolerance pattern preventing cascading failures across microservices."
        ),
    ),
)

