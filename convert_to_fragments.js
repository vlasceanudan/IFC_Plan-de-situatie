const fs = require('fs');
const path = require('path');
const { IfcImporter } = require('@thatopen/fragments');

async function main() {
  const [input, output] = process.argv.slice(2);
  if (!input || !output) {
    console.error('Usage: node convert_to_fragments.js <input.ifc> <output.ifcfrag>');
    process.exit(1);
  }

  const bytes = fs.readFileSync(input);
  const importer = new IfcImporter();
  importer.wasm = { absolute: true, path: path.resolve(__dirname, 'node_modules/web-ifc/') + '/' };

  try {
    const frag = await importer.process({ bytes });
    fs.writeFileSync(output, Buffer.from(frag));
  } catch (err) {
    console.error(err);
    process.exit(1);
  }
}

main();
