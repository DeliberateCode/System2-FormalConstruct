## Style Requirements for Proof Formalization Context

### Frame Problems Using ProblemSpec Vocabulary

Organize problem descriptions around ProblemSpec fields:

- **`problem_domain`**: State the domain classification explicitly (continuous_optimization, non_cooperative_game, cooperative_game, or discrete)
- **`spaces`**: Describe base types and topological properties
- **`variables`**: State classification (endogenous, exogenous, strategy_profile), bounds (lower/upper, strict/non-strict), and space membership
- **`functions`**: State properties (convex, strictly convex, linear, continuous) and domain/codomain
- **`objective`**: State direction (minimize, maximize, equilibrium, pareto_optimal) and expression

### Use Precise Mathematical Terminology

Use terminology consistent with the supported domain families:

- Write "strictly convex" rather than informal approximations like "very curved" or "bending upward"
- Write "Nash equilibrium" rather than "stable state" or "balance point"
- Write "Pareto optimal" rather than "best for everyone"
- Use standard notation for bounds: "x >= 0" for non-strict, "x > 0" for strict inequality
- State function properties using their formal names: `StrictConvex`, `Convex`, `Linear`, `Continuous`

### Explicit Declarations

When describing variables, always state classification, bounds, and space membership as separate attributes. When describing functions, always state properties and domain/codomain as separate attributes. Implicit assumptions lead to ProblemSpec extraction errors.
