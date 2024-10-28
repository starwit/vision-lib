package de.starwit.testing;

import java.io.Closeable;
import java.io.IOException;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;

import de.starwit.visionapi.Sae.SaeMessage;

public class SaeDump implements Iterable<SaeMessage>, Closeable {

    private Path path;
    private List<SaeDumpIterator> iterators = new ArrayList<>();
    
    public SaeDump(Path path) {
        this.path = path;
    }
    
    @Override
    public Iterator<SaeMessage> iterator() {
        SaeDumpIterator iter = new SaeDumpIterator(this.path);
        this.iterators.add(iter);
        return iter;
    }

    @Override
    public void close() throws IOException {
        this.iterators.forEach(SaeDumpIterator::close);
        this.iterators.clear();
    }
}
