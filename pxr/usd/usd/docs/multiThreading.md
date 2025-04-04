# Threading Model and Performance Considerations {#Usd_Page_MultiThreading}

stl threading model : multiple readers *or* a single writer

Although some clients may find it inconvenient that they must provide their
own exclusive sections for writing to the same stage from multiple threads,
what *all* clients get in exchange is a thread-efficient USD core, in which
nearly all read access to USD data is lockless.

## Thread-safety Guarantee {#Usd_ThreadSafetyModel}

Any UsdStage-mutating or SdfLayer-mutating operation considered a write.  
UsdStage::Load() and UsdPrim::Load() (and unload) are considered write 
operations because they mutate a stage's contents, even though no scene 
description is authored.

Although it is not possible for multiple threads to simultaneously write
"to the same stage", it is safe for different threads to write simultaneously
to *different* stages.  Note the subtlety here of what "different stages"
means, however.  If stages A and B consist each solely of layers A.usd and
B.usd, respectively, then two different threads are entirely free to mutate
the two stages simultaneously.  However, if A.usd and B.usd both sublayer
C.usd, the stages A and B, while distinct, share dependence on C.usd.  If one
thread, therefore, is mutating C.usd, then **no other thread 
can mutate A.usd or B.usd** because either would cause simultaneous changes
to either stage A or stage B.
