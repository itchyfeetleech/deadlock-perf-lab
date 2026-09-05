# Release validation

Version 0.1.0 was checked on Linux with native Steam, Proton and MangoHud on 5 September 2026.

- 48 automated tests cover capture parsing, statistics, scheduling, recovery, imports, report integrity and convar sweeps.
- Two three-run live replay sessions completed, including baseline → changed GameInfo → baseline. The game closed after each capture and all temporary configuration was restored.
- The GameInfo sequence had a median iteration time of 34.7 seconds with a 10-second sample, 5-second warm-up and 1-second settle. An earlier 57-capture sweep had a 49.7-second median with the same sample and warm-up and a 2-second settle. This is about 30% less wall time in this local check, not a controlled cross-machine speed guarantee.
- Cold launch/load times varied substantially: two iterations in the first readiness check took 73–81 seconds. Use `dpl timings` to estimate your own sweep.
- The synthetic report was inspected in a browser, including the capture selector. Its values are examples, not game measurements.

These live smoke tests establish that capture, iteration and restoration worked on the tested installation. They do not validate an optimization winner. Camera and playback progression still need operator review; one screening round cannot support a directional verdict. Game updates may change console messages or configuration behavior.

For 50 treatments, a one-round screen schedules 52 launches versus 156 for three rounds. Confirm a shortlist with longer repeated captures rather than treating the screen as a final ranking.
