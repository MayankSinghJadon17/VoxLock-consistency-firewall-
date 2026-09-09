export default function GuaranteeBanner() {
  return (
    <section
      className="guarantee-banner"
      aria-label="VoxLock core guarantee"
    >
      <div className="banner-index">Lock</div>

      <div className="guarantee-content">
        <p className="eyebrow">VOXLOCK CORE GUARANTEE</p>

        <h1>
          Superseded intent cannot
          <br className="desktop-only" /> become spoken reality.
        </h1>

        <p className="banner-copy">
          Every request is versioned. When the user changes their mind,
          computation may be cancelled or finish later — but stale output
          cannot cross the speech boundary.
        </p>
      </div>

      <div className="banner-symbol" aria-hidden="true">
        ◇
      </div>
    </section>
  )
}